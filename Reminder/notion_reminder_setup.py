#!/usr/bin/env python3
"""
Notion Reminder System Builder

Creates this under an existing Notion page:

Your Page
└── 🔔 Reminder Log
    ├── Reminder (Title)
    ├── 📸 Media (Files & media)
    ├── 🕐 Time to Remind (Date)
    ├── 📝 Reason (Rich text)
    ├── 📊 Status (Status)
    └── Created (Created time)

Install:
    pip install -U notion-client

Before running:
1. Create a Notion integration.
2. Connect/share your existing ROOT PAGE with that integration.
3. Run this file.
4. Paste the integration token when prompted.
5. Paste the URL or ID of the page you created.

Never send your Notion token to anyone, including ChatGPT.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import sys
from pathlib import Path

from notion_client import Client


IDS_FILE = Path(__file__).with_name("notion_reminder_system_ids.json")


def page_id_from_url(value: str) -> str:
    value = value.strip()

    # Accept a normal 32-character Notion ID from a URL.
    m = re.search(r"([0-9a-fA-F]{32})", value)
    if m:
        raw = m.group(1)
        return (
            f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-"
            f"{raw[16:20]}-{raw[20:]}"
        )

    # Or an already-hyphenated UUID.
    m = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        value,
    )
    if m:
        return m.group(1)

    raise ValueError("Could not find a Notion page ID in that URL/ID.")


def get_token() -> str:
    file_path = r"D:\Notion\ENV_FILES.json"
    with open(file_path, "r") as f:
        data = json.load(f)
        NOTION_TOKEN = data["NOTION_TOKEN"]
    return NOTION_TOKEN


def add_intro(notion: Client, page_id: str) -> None:
    blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": (
                            "Capture something now. Add when to remember it. "
                            "Let Notion remind you later."
                        )
                    },
                }],
                "icon": {"type": "emoji", "emoji": "🔔"},
            },
        },
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "Quick workflow"},
                }]
            },
        },
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": "📸 Add the screenshot or image."
                    },
                }]
            },
        },
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": "🕐 Set the exact reminder date and time."
                    },
                }]
            },
        },
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": "📝 Write why you need the reminder."
                    },
                }]
            },
        },
        {
            "object": "block",
            "type": "divider",
            "divider": {},
        },
    ]

    notion.blocks.children.append(block_id=page_id, children=blocks)


def create_reminder_database(notion: Client, parent_page_id: str) -> dict:
    properties = {
        "Reminder": {"title": {}},
        "📸 Media": {"files": {}},
        "🕐 Time to Remind": {"date": {}},
        "📝 Reason": {"rich_text": {}},
        "📊 Status": {
            "status": {
                "options": [
                    {"name": "Upcoming", "color": "blue"},
                    {"name": "Done", "color": "green"},
                    {"name": "Cancelled", "color": "gray"},
                ]
            }
        },
        "Created": {"created_time": {}},
    }

    return notion.databases.create(
        parent={
            "type": "page_id",
            "page_id": parent_page_id,
        },
        title=[{
            "type": "text",
            "text": {"content": "🔔 Reminder Log"},
        }],
        icon={"type": "emoji", "emoji": "🔔"},
        properties=properties,
    )


def main() -> None:
    print("=" * 60)
    print("🔔 NOTION REMINDER SYSTEM BUILDER")
    print("=" * 60)

    if IDS_FILE.exists():
        print(f"\nAn earlier setup file exists: {IDS_FILE}")
        choice = input("Create another copy anyway? [y/N]: ").strip().lower()
        if choice != "y":
            print("Stopped.")
            return

    token = get_token()

    root_input = "https://www.notion.so/Essential-Space-3dce46567a3a80949b51c158be338e89?source=copy_link"
    root_page_id = page_id_from_url(root_input)
    notion = Client(auth=token)

    print("\n🔎 Checking access...")
    notion.pages.retrieve(page_id=root_page_id)
    print("✓ Page access confirmed.")

    print("✨ Adding a clean introduction...")
    add_intro(notion, root_page_id)

    print("🗃️ Creating Reminder Log database...")
    db = create_reminder_database(notion, root_page_id)
    db_id = db["id"]

    ids = {
        "root_page_id": root_page_id,
        "database_id": db_id,
        "database_url": db.get("url", ""),
        "properties": [
            "Reminder",
            "📸 Media",
            "🕐 Time to Remind",
            "📝 Reason",
            "📊 Status",
            "Created",
        ],
    }

    IDS_FILE.write_text(
        json.dumps(ids, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("🎉 DONE")
    print("=" * 60)
    print("\nCreated:")
    print("  Your existing page")
    print("    └── 🔔 Reminder Log")
    print("         ├── 📸 Media")
    print("         ├── 🕐 Time to Remind")
    print("         ├── 📝 Reason")
    print("         ├── 📊 Status")
    print("         └── Created")

    if db.get("url"):
        print("\nDatabase:")
        print(db["url"])

    print(f"\nIDs saved to: {IDS_FILE}")

    print("\nNEXT:")
    print("Create one test reminder and set the date/time a few minutes")
    print("from now. Then confirm the Notion notification arrives on your phone.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n❌ SETUP FAILED")
        print("-" * 60)
        print(exc)
        print("\nTry:")
        print("  pip install -U notion-client")
        print("and make sure your integration is connected to the page.")
        sys.exit(1)
