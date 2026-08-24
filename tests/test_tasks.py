from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.lead import Lead, LeadStatus, LeadEventType
from app.tasks.lead_tasks import (
    create_or_update_bigin_lead_task,
    run_full_reconciliation_task,
)

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class TestCeleryTasks:

    def setup_method(self):
        Base.metadata.create_all(bind=engine)
        db = TestingSessionLocal()
        lead = Lead(
            customer_name="Kavita Roy",
            phone="+919876543210",
            message="FastAPI task test",
            msg91_contact_id="CNT_001",
            source="WhatsApp",
            status=LeadStatus.RECEIVED.value,
        )
        db.add(lead)
        db.commit()
        self.lead_id = lead.id
        db.close()

    def teardown_method(self):
        Base.metadata.drop_all(bind=engine)

    @patch("app.tasks.lead_tasks.SessionLocal", side_effect=TestingSessionLocal)
    @patch("app.tasks.lead_tasks.BiginClient")
    def test_create_or_update_bigin_lead_task_creates_new(self, mock_bigin_class, mock_session_local):
        mock_instance = MagicMock()
        mock_instance.create_lead.return_value = "BIGIN_NEW_99"
        mock_bigin_class.return_value = mock_instance

        create_or_update_bigin_lead_task(self.lead_id)

        db = TestingSessionLocal()
        lead = db.query(Lead).filter(Lead.id == self.lead_id).first()
        assert lead.status == LeadStatus.CREATED.value
        assert lead.bigin_lead_id == "BIGIN_NEW_99"
        mock_instance.create_lead.assert_called_once()
        mock_instance.update_lead.assert_not_called()
        db.close()

    @patch("app.tasks.lead_tasks.SessionLocal", side_effect=TestingSessionLocal)
    @patch("app.tasks.lead_tasks.BiginClient")
    def test_create_or_update_bigin_lead_task_updates_existing(self, mock_bigin_class, mock_session_local):
        db = TestingSessionLocal()
        lead = db.query(Lead).filter(Lead.id == self.lead_id).first()
        lead.bigin_lead_id = "EXISTING_BIGIN_ID_100"
        db.commit()
        db.close()

        mock_instance = MagicMock()
        mock_instance.update_lead.return_value = "EXISTING_BIGIN_ID_100"
        mock_bigin_class.return_value = mock_instance

        create_or_update_bigin_lead_task(self.lead_id)

        db = TestingSessionLocal()
        updated_lead = db.query(Lead).filter(Lead.id == self.lead_id).first()
        assert updated_lead.status == LeadStatus.CREATED.value
        mock_instance.update_lead.assert_called_once()
        mock_instance.create_lead.assert_not_called()
        db.close()

    @patch("app.tasks.lead_tasks.SessionLocal", side_effect=TestingSessionLocal)
    @patch("app.tasks.lead_tasks.create_or_update_bigin_lead_task.delay")
    @patch("app.tasks.lead_tasks.MSG91Client")
    def test_run_full_reconciliation_task_idempotent(self, mock_msg91_class, mock_task_delay, mock_session_local):
        mock_msg91_instance = MagicMock()
        mock_msg91_instance.fetch_all_contacts.return_value = [
            {"phone": "+919876543210", "customer_name": "Kavita Roy", "msg91_contact_id": "CNT_001"},
            {"phone": "+919876543211", "customer_name": "New User", "msg91_contact_id": "CNT_002"},
        ]
        mock_msg91_class.return_value = mock_msg91_instance

        # Run 1
        res1 = run_full_reconciliation_task()
        assert res1["status"] == "success"
        assert res1["new_leads_created"] == 1  # only +919876543211 is new

        db = TestingSessionLocal()
        assert db.query(Lead).count() == 2
        db.close()

        # Run 2 (Idempotency check)
        res2 = run_full_reconciliation_task()
        assert res2["status"] == "success"
        assert res2["new_leads_created"] == 0  # no new leads created on 2nd run

        db = TestingSessionLocal()
        assert db.query(Lead).count() == 2
        db.close()
