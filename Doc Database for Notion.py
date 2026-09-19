"""
Notion Document Manager — Bulk Importer
----------------------------------------
Creates one page per document/item in your Notion "Document Manager" database,
using the list you pasted (Name + priority Type) as the seed data.

WHAT THIS DOES
- Sets the page title (Name) for every row.
- Sets a "Priority" tag (Must-have / Probably-have / Can-have / Maybe) into
  whichever property you tell it to (Tags multi-select by default), so the
  🔴🟠🟡🟣 categorisation from your table isn't lost.
- Leaves everything else (Owner, Files, Status, Effective Date, etc.) empty —
  you fill those in per-document once you upload your personal details.
- Skips rows that already exist in the database (matched by title), so it's
  safe to re-run after you add more documents later.

SETUP (one-time)
1. Create an integration: https://www.notion.so/my-integrations -> "New integration"
   Copy the "Internal Integration Secret" (starts with "secret_" or "ntn_").
2. Open your "Documents" database in Notion -> "..." menu (top right) ->
   "Connections" -> add the integration you just created. Without this step
   the API call will fail with "object not found" even with a valid token.
3. Get the database ID: open the database as a full page, copy the URL.
   It looks like:
     https://www.notion.so/myworkspace/<DATABASE_ID>?v=<view_id>
   DATABASE_ID is the 32-character hex string right after the workspace name
   (dashes optional).
4. pip install notion-client --break-system-packages
5. Set the two environment variables below (or hardcode them just for a
   local one-off run — don't commit real secrets anywhere).

USAGE
    export NOTION_TOKEN="secret_xxx"
    export NOTION_DATABASE_ID="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    python3 notion_import.py

    # Dry run first (prints what it would create, makes no API calls):
    python3 notion_import.py --dry-run
"""

import os
import sys
import argparse
import json
from notion_client import Client
from notion_client.errors import APIResponseError

# ---------------------------------------------------------------------------
# 1. CONFIG — adjust these to match your database's actual property names.
# ---------------------------------------------------------------------------

# The Notion property that holds each row's priority marker.
# Must be a "Multi-select" or "Select" property in your DB.
# Change to "Type" if you'd rather store priority there instead of Tags.
PRIORITY_PROPERTY_NAME = "Tags"
PRIORITY_PROPERTY_TYPE = "multi_select"  # "multi_select" or "select"

# The title property is almost always called "Name" in Notion — change only
# if your DB's title column has a different label.
TITLE_PROPERTY_NAME = "Name"

# ---------------------------------------------------------------------------
# 2. DATA — parsed from your table. (name, priority_label)
# ---------------------------------------------------------------------------

DOCUMENTS = [
    ("Aadhaar Card", "Must-have"),
    ("PAN Card", "Must-have"),
    ("Birth Certificate", "Must-have"),
    ("Passport", "Must-have"),
    ("Driving Licence", "Must-have"),
    ("Voter ID / EPIC", "Must-have"),
    ("10th Marksheet / Certificate", "Must-have"),
    ("12th Marksheet / Certificate", "Must-have"),
    ("B.Tech Degree Certificate", "Must-have"),
    ("B.Tech Consolidated Marksheet", "Must-have"),
    ("B.Tech Semester Mark Sheets", "Probably-have"),
    ("Transfer Certificate (TC)", "Probably-have"),
    ("Migration Certificate", "Can-have / Situational"),
    ("Personal Email ID", "Must-have"),
    ("Personal Mobile Number", "Must-have"),
    ("Bank Account", "Must-have"),
    ("Bank Passbook / Statements", "Must-have"),
    ("Salary Slips", "Must-have"),
    ("Form 16", "Must-have"),
    ("Income Tax Return (ITR) Acknowledgements", "Must-have"),
    ("ITR Computation / Tax Documents", "Probably-have"),
    ("UAN / EPF Account Details", "Must-have for salaried employee"),
    ("PF Passbook / Statement", "Probably-have"),
    ("Employment Offer Letter", "Must-have"),
    ("Appointment Letter", "Must-have"),
    ("Employment Agreement", "Probably-have"),
    ("Experience Certificate", "Must-have"),
    ("Relieving Letter", "Must-have"),
    ("Promotion / Designation Letters", "Probably-have"),
    ("Increment / Appraisal Letters", "Probably-have"),
    ("Full & Final Settlement Document", "Must-have when leaving a company"),
    ("Employment Background-Verification Documents", "Probably-have"),
    ("DigiLocker Account", "Must-have / Highly recommended"),
    ("Rental Agreement", "Probably-have"),
    ("Electricity / Utility Bill", "Probably-have"),
    ("Address Proofs", "Probably-have"),
    ("Nativity Certificate", "Can-have / Situational"),
    ("Residence Certificate", "Can-have / Situational"),
    ("Income Certificate", "Can-have / Situational"),
    ("Community / Caste Certificate", "Can-have / If applicable"),
    ("OBC Certificate", "Maybe / If applicable"),
    ("EWS Certificate", "Maybe / If applicable"),
    ("First Graduate Certificate", "Can-have / If applicable"),
    ("Disability Certificate", "Maybe / If applicable"),
    ("Police Clearance Certificate (PCC)", "Maybe / Travel-visa specific"),
    ("Health Insurance Policy", "Probably-have"),
    ("Health Insurance Card", "Probably-have"),
    ("Important Medical Records", "Can-have"),
    ("Vaccination Records", "Can-have"),
    ("Blood Group Record", "Can-have"),
    ("Vehicle RC", "Probably-have / If vehicle owned"),
    ("Vehicle Insurance", "Probably-have / If vehicle owned"),
    ("PUC Certificate", "Probably-have / If vehicle owned"),
    ("Vehicle Purchase Invoice", "Can-have / If vehicle owned"),
    ("Vehicle Service Records", "Can-have / If vehicle owned"),
    ("International Driving Permit (IDP)", "Maybe / If driving abroad"),
    ("Visa Documents", "Maybe / Country-specific"),
    ("Previous Passports", "Can-have / If applicable"),
    ("Travel Insurance", "Maybe / Trip-specific"),
    ("Mutual Fund Statements", "Can-have / If investing"),
    ("Demat Account Details", "Can-have / If investing"),
    ("Stock Contract Notes", "Can-have / If investing"),
    ("Capital Gains Statements", "Can-have / If investing"),
    ("NPS / PRAN Details", "Maybe / If using NPS"),
    ("Life Insurance Policy", "Can-have / If applicable"),
    ("Insurance Premium Receipts", "Can-have"),
    ("Bank Nominee Details", "Must-have"),
    ("PF Nominee Details", "Must-have"),
    ("Insurance Nominee Details", "Must-have"),
    ("Investment Nominee Details", "Probably-have"),
    ("Marriage Certificate", "Maybe / Future"),
    ("Spouse Documents", "Maybe / Future"),
    ("Children's Birth Certificates", "Maybe / Future"),
    ("Children's Aadhaar / Passport", "Maybe / Future"),
    ("Property Sale Deed", "Maybe / If property owned"),
    ("Encumbrance Certificate (EC)", "Maybe / If property owned"),
    ("Patta", "Maybe / If property owned"),
    ("Property Tax Receipts", "Maybe / If property owned"),
    ("Building Approval / Plan", "Maybe / If property owned"),
    ("Property Loan Documents", "Maybe / If applicable"),
    ("Will", "Maybe / Future"),
    ("Legal Heir Certificate", "Maybe / Situational"),
    ("Business / GST Documents", "Maybe / If you start a business"),
    ("Professional Licence / Registration", "Maybe / If applicable"),
]


def build_properties(name: str, priority: str) -> dict:
    props = {
        TITLE_PROPERTY_NAME: {
            "title": [{"text": {"content": name}}]
        }
    }
    if PRIORITY_PROPERTY_TYPE == "multi_select":
        props[PRIORITY_PROPERTY_NAME] = {
            "multi_select": [{"name": priority}]
        }
    elif PRIORITY_PROPERTY_TYPE == "select":
        props[PRIORITY_PROPERTY_NAME] = {
            "select": {"name": priority}
        }
    return props


def get_data_source_id(notion: Client, database_id: str) -> str:
    """
    Notion's 2025-09-03+ API split databases into "data sources" (a database
    is now a container that can hold one or more data sources, and pages
    live under a data source, not the database directly). We look up the
    database's first data source and query/create against that instead.
    """
    db = notion.databases.retrieve(database_id=database_id)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        raise RuntimeError(
            "This database has no data sources visible to the integration. "
            "Make sure the integration has access (... menu -> Connections)."
        )
    if len(data_sources) > 1:
        print(
            f"Note: database has {len(data_sources)} data sources; "
            f"using the first one ('{data_sources[0].get('name')}')."
        )
    return data_sources[0]["id"]


def get_existing_titles(notion: Client, data_source_id: str) -> set:
    """Fetch existing page titles so re-runs don't create duplicates."""
    titles = set()
    cursor = None
    while True:
        resp = notion.data_sources.query(
            data_source_id=data_source_id,
            start_cursor=cursor,
            page_size=100,
        )
        for page in resp["results"]:
            prop = page["properties"].get(TITLE_PROPERTY_NAME, {})
            texts = prop.get("title", [])
            if texts:
                titles.add(texts[0]["plain_text"])
        if resp.get("has_more"):
            cursor = resp["next_cursor"]
        else:
            break
    return titles

def get_notion_token():
    file_path = r"D:\Notion\ENV_FILES.json"
    with open(file_path, "r") as f:
        data = json.load(f)
        NOTION_TOKEN = data["NOTION_TOKEN"]
    return NOTION_TOKEN

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be created without calling the Notion API."
    )
    args = parser.parse_args()

    if args.dry_run:
        print(f"Would create {len(DOCUMENTS)} pages:\n")
        for name, priority in DOCUMENTS:
            print(f"  - {name}  [{priority}]")
        return

    token = get_notion_token()
    database_id = "c94e4656-7a3a-832e-bbfc-81729607304f"

    if not token or not database_id:
        print(
            "Missing NOTION_TOKEN or NOTION_DATABASE_ID environment variables.\n"
            "See the setup instructions at the top of this file, then run:\n"
            "  export NOTION_TOKEN=secret_xxx\n"
            "  export NOTION_DATABASE_ID=xxxxxxxx...\n"
            "  python3 notion_import.py\n"
            "\nOr try `python3 notion_import.py --dry-run` first to preview."
        )
        sys.exit(1)

    notion = Client(auth=token)

    try:
        data_source_id = get_data_source_id(notion, database_id)
        print("Checking for existing entries (to avoid duplicates)...")
        existing = get_existing_titles(notion, data_source_id)
    except APIResponseError as e:
        print(f"Could not read the database: {e}")
        print(
            "Double-check: (1) the database ID is correct, and "
            "(2) you've shared the database with your integration "
            "via '...' -> Connections in Notion."
        )
        sys.exit(1)

    created, skipped, failed = 0, 0, 0
    for name, priority in DOCUMENTS:
        if name in existing:
            skipped += 1
            continue
        try:
            notion.pages.create(
                parent={"type": "data_source_id", "data_source_id": data_source_id},
                properties=build_properties(name, priority),
            )
            created += 1
            print(f"  + {name}")
        except APIResponseError as e:
            failed += 1
            print(f"  ! Failed on '{name}': {e}")

    print(f"\nDone. Created: {created}  Skipped (already existed): {skipped}  Failed: {failed}")


if __name__ == "__main__":
    main()