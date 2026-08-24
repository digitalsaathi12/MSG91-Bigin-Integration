import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db.base import Base

class LeadStatus(str, enum.Enum):
    RECEIVED = 'RECEIVED'
    PROCESSING = 'PROCESSING'
    CREATED = 'CREATED'
    FAILED = 'FAILED'
    THROTTLED = 'THROTTLED'
    RETRYING = 'RETRYING'

class LeadEventType(str, enum.Enum):
    CONTACT_ADDED = 'CONTACT_ADDED'
    MESSAGE_SENT = 'MESSAGE_SENT'
    MESSAGE_RECEIVED = 'MESSAGE_RECEIVED'

class Lead(Base):
    __tablename__ = 'leads'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_name = Column(String(255), nullable=True)
    phone = Column(String(50), unique=True, index=True, nullable=False)
    message = Column(Text, nullable=True, default='')
    last_event_type = Column(String(50), nullable=True, default=LeadEventType.MESSAGE_RECEIVED.value)
    msg91_contact_id = Column(String(255), nullable=True)
    source = Column(String(100), nullable=False, default='WhatsApp')
    bigin_lead_id = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default=LeadStatus.RECEIVED.value, index=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_event_at = Column(DateTime, nullable=True, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Lead id={self.id} phone='{self.phone}' status='{self.status}'>"
