"""
Bigin API Discovery Script
Calls three settings endpoints to find:
  1. All module api_names (look for Pipelines module and its layouts)
  2. All fields for the Pipelines module (focus on Sub_Pipeline pick_list_values)
  3. All layouts for the Pipelines module (find "All Leads - We Do Finserv" and its ID)

Run with: python scripts/discover_bigin.py
"""

import sys
import json
import os

# Add project root to path so app.* imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.services.oauth_manager import ZohoOAuthManager
import requests


def pretty(label: str, data: dict):
    print(f"\n{'=' * 70}")
    print(f" {label}")
    print("=" * 70)
    print(json.dumps(data, indent=2))


def get(token: str, url: str) -> dict:
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type": "application/json",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    print(f"  HTTP {resp.status_code}  ->  {url}")
    return resp.json()


def main():
    print("=" * 70)
    print(" STEP 0: Obtaining Bigin Access Token")
    print("=" * 70)

    oauth = ZohoOAuthManager(
        client_id=settings.BIGIN_CLIENT_ID,
        client_secret=settings.BIGIN_CLIENT_SECRET,
        refresh_token=settings.BIGIN_REFRESH_TOKEN,
        accounts_url=settings.BIGIN_ACCOUNTS_URL,
    )

    try:
        token = oauth.refresh_access_token()
        print(f"[OK] Token obtained (first 20 chars): {token[:20]}...")
    except Exception as e:
        print(f"[FAILED] {e}")
        sys.exit(1)

    api = settings.BIGIN_API_DOMAIN.rstrip("/")

    # -----------------------------------------------------------------------
    # CALL 1 — List all modules
    # -----------------------------------------------------------------------
    modules_data = get(token, f"{api}/bigin/v2/settings/modules")
    pretty("CALL 1: GET /bigin/v2/settings/modules  (RAW JSON)", modules_data)

    print("\n--- Module Summary (api_name | module_name) ---")
    pipelines_api_name = None
    for m in modules_data.get("modules", []):
        api_name = m.get("api_name", "N/A")
        mod_name = m.get("module_name", "N/A")
        marker = ""
        if "pipeline" in api_name.lower() or "pipeline" in mod_name.lower():
            marker = "  <<<<  PIPELINES MODULE"
            pipelines_api_name = api_name
        print(f"  {api_name:<35} | {mod_name}{marker}")

        # Print layouts if present inside the module object
        layouts = m.get("layouts") or m.get("related_list_properties", {}).get("layouts")
        if layouts and marker:
            print(f"    Layouts embedded in module response:")
            for lay in layouts:
                print(f"      id={lay.get('id')}  name={lay.get('name')}")

    if pipelines_api_name:
        print(f"\n[Detected Pipelines module api_name: '{pipelines_api_name}']")
    else:
        print("\n[WARNING] No module with 'pipeline' in api_name/module_name found — using 'Pipelines']")
        pipelines_api_name = "Pipelines"

    # -----------------------------------------------------------------------
    # CALL 2 — Fields for Pipelines module
    # -----------------------------------------------------------------------
    fields_data = get(token, f"{api}/bigin/v2/settings/fields?module={pipelines_api_name}")
    pretty(f"CALL 2: GET /bigin/v2/settings/fields?module={pipelines_api_name}  (RAW JSON)", fields_data)

    print(f"\n--- Field Summary for '{pipelines_api_name}' (api_name | field_label | data_type) ---")
    interesting = ["sub_pipeline", "pipeline", "stage", "deal_name", "pipeline_stage", "layout"]
    for f in fields_data.get("fields", []):
        fname   = f.get("api_name", "N/A")
        label   = f.get("field_label", "N/A")
        dtype   = f.get("data_type", "N/A")
        marker  = "  <<<<" if any(k in fname.lower() for k in interesting) else ""
        print(f"  {fname:<35} | {label:<30} | {dtype}{marker}")

        # For Sub_Pipeline and similar, print pick_list_values in full
        if any(k in fname.lower() for k in interesting):
            plv = f.get("pick_list_values") or []
            if plv:
                print(f"    pick_list_values for '{fname}':")
                for pv in plv:
                    print(f"      id={pv.get('id')}  display_value={pv.get('display_value')}  actual_value={pv.get('actual_value')}")
            # Also print full field JSON for these key fields
            print(f"    Full field definition for '{fname}':")
            print(f"    {json.dumps(f, indent=6)}")

    # -----------------------------------------------------------------------
    # CALL 3 — Layouts for Pipelines module
    # -----------------------------------------------------------------------
    layouts_data = get(token, f"{api}/bigin/v2/settings/layouts?module={pipelines_api_name}")
    pretty(f"CALL 3: GET /bigin/v2/settings/layouts?module={pipelines_api_name}  (RAW JSON)", layouts_data)

    print(f"\n--- Layout Summary for '{pipelines_api_name}' ---")
    target_keywords = ["all leads", "we do finserv", "finserv"]
    for lay in layouts_data.get("layouts", []):
        lay_id   = lay.get("id", "N/A")
        lay_name = lay.get("name", "N/A")
        match    = any(kw in lay_name.lower() for kw in target_keywords)
        marker   = "  <<<<  TARGET LAYOUT" if match else ""
        print(f"  id={lay_id}  name={lay_name}{marker}")
        if match:
            print(f"  Full layout JSON for '{lay_name}':")
            print(f"  {json.dumps(lay, indent=4)}")

    print("\n[Done] Copy the layout id and Sub_Pipeline pick_list values above into .env")


if __name__ == "__main__":
    main()
