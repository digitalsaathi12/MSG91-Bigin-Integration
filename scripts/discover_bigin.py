"""
Issue 1 - Discovery Script: Bigin Modules & Fields
Run with: python scripts/discover_bigin.py
"""

import sys
import json
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.services.oauth_manager import ZohoOAuthManager
import requests

def main():
    print("=" * 70)
    print(" STEP 1: Obtaining Bigin Access Token")
    print("=" * 70)

    oauth = ZohoOAuthManager(
        client_id=settings.BIGIN_CLIENT_ID,
        client_secret=settings.BIGIN_CLIENT_SECRET,
        refresh_token=settings.BIGIN_REFRESH_TOKEN,
        accounts_url=settings.BIGIN_ACCOUNTS_URL,
    )

    try:
        token = oauth.refresh_access_token()
        print(f"[OK] Access token obtained (first 20 chars): {token[:20]}...")
    except Exception as e:
        print(f"[FAILED] Could not obtain access token: {e}")
        sys.exit(1)

    api_domain = settings.BIGIN_API_DOMAIN.rstrip("/")
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type": "application/json",
    }

    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(" STEP 2: GET /bigin/v2/settings/modules")
    print("=" * 70)

    modules_url = f"{api_domain}/bigin/v2/settings/modules"
    resp = requests.get(modules_url, headers=headers, timeout=15)
    print(f"HTTP Status: {resp.status_code}")

    modules_json = resp.json()
    print("\n--- Full JSON Response ---")
    print(json.dumps(modules_json, indent=2))

    # Print a concise summary table
    print("\n--- Module Summary (api_name | module_name) ---")
    modules_list = modules_json.get("modules", [])
    for m in modules_list:
        api_name = m.get("api_name", "N/A")
        module_name = m.get("module_name", "N/A")
        print(f"  {api_name:<30} | {module_name}")

    # -----------------------------------------------------------------------
    # Pick the Contacts module (which maps to Bigin's pipeline-based records)
    # We'll fetch fields for both "Contacts" and "Leads" to compare
    target_modules = ["Contacts", "Leads"]
    for mod in target_modules:
        print(f"\n{'=' * 70}")
        print(f" STEP 3: GET /bigin/v2/settings/fields?module={mod}")
        print("=" * 70)

        fields_url = f"{api_domain}/bigin/v2/settings/fields?module={mod}"
        freq = requests.get(fields_url, headers=headers, timeout=15)
        print(f"HTTP Status: {freq.status_code}")

        fields_json = freq.json()
        print("\n--- Full JSON Response ---")
        print(json.dumps(fields_json, indent=2))

        # Print concise field summary
        print(f"\n--- Field Summary for module '{mod}' (api_name | field_label | data_type) ---")
        fields_list = fields_json.get("fields", [])
        for f in fields_list:
            fname = f.get("api_name", "N/A")
            label = f.get("field_label", "N/A")
            dtype = f.get("data_type", "N/A")
            # Highlight stage/pipeline/name fields
            highlight = " <-- STAGE/PIPELINE/NAME" if any(k in fname.lower() for k in ["stage", "pipeline", "last_name", "name", "contact_name"]) else ""
            print(f"  {fname:<35} | {label:<30} | {dtype}{highlight}")

if __name__ == "__main__":
    main()
