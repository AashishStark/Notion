import os
import sys
import json
import time
from pathlib import Path
from notion_client import Client
from notion_client.errors import APIResponseError

# Set stdout encoding for Windows terminal unicode support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# ============================================================
# CONFIGURATION
# ============================================================

ENV_FILE = r"D:\Notion\ENV_FILES.json"
IDS_FILE = Path(__file__).with_name("notion_reminder_system_ids.json")
REMINDER_JSON = Path(__file__).with_name("reminder.json")


def get_notion_token():
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data["NOTION_TOKEN"]


def get_system_ids():
    if IDS_FILE.exists():
        with open(IDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "root_page_id": "3dce4656-7a3a-8094-9b51-c158be338e89",
        "database_id": "5a5ae58d-f632-48d4-aacd-c7fe446dc787",
    }


NOTION_TOKEN = get_notion_token()
client = Client(auth=NOTION_TOKEN)
system_ids = get_system_ids()
DATABASE_ID = system_ids.get("database_id", "5a5ae58d-f632-48d4-aacd-c7fe446dc787")


def create_reminder_entry(
    title: str,
    media_url: str,
    remind_time_iso: str,
    reason: str,
    status: str = "Upcoming",
    icon_emoji: str = "📌",
):
    """Creates a new page under the Notion Reminder Log database replicating Nothing 3a Essential Space capture.

    Mandatory properties:
    1. Media File (Image) -> 📸 Media
    2. Time to Remind -> 🕐 Time to Remind
    3. Reason -> 📝 Reason
    + Title -> Reminder
    + Status -> 📊 Status
    """
    properties = {
        "Reminder": {
            "title": [
                {
                    "type": "text",
                    "text": {"content": title},
                }
            ]
        },
        "📸 Media": {
            "files": [
                {
                    "name": f"{title.lower().replace(' ', '_')}_snapshot.jpg",
                    "type": "external",
                    "external": {"url": media_url},
                }
            ]
        },
        "🕐 Time to Remind": {
            "date": {
                "start": remind_time_iso,
            }
        },
        "📝 Reason": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": reason},
                }
            ]
        },
        "📊 Status": {
            "status": {
                "name": status,
            }
        },
    }

    # Visual body content representing Nothing Essential Space captured card
    children = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": f"Essential Space Reminder: {reason}"},
                    }
                ],
                "icon": {"type": "emoji", "emoji": icon_emoji},
                "color": "gray_background",
            },
        },
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "📸 Captured Media"},
                    }
                ]
            },
        },
        {
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": media_url},
            },
        },
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "⏰ Reminder Details"},
                    }
                ]
            },
        },
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "Scheduled Time: "},
                        "annotations": {"bold": True},
                    },
                    {"type": "text", "text": {"content": remind_time_iso}},
                ]
            },
        },
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "Reason / Trigger: "},
                        "annotations": {"bold": True},
                    },
                    {"type": "text", "text": {"content": reason}},
                ]
            },
        },
    ]

    new_page = client.pages.create(
        parent={"database_id": DATABASE_ID},
        icon={"type": "emoji", "emoji": icon_emoji},
        cover={"type": "external", "external": {"url": media_url}},
        properties=properties,
        children=children,
    )
    print(f"✓ Created reminder page: {title} (ID: {new_page['id']})")
    return new_page


def main():
    print("=" * 60)
    print("🚀 UPDATING ESSENTIAL SPACE REMINDER DATABASE")
    print("=" * 60)

    # Sample reminders representing Essential Space AI captures
    sample_reminders = [
        {
            "title": "✈️ Flight to Mumbai - Gate & Check-in",
            "media_url": "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=800",
            "remind_time_iso": "2026-09-16T09:00:00+05:30",
            "reason": "Check-in opens 24h prior. Confirm seat selection and download boarding pass.",
            "status": "Upcoming",
            "icon_emoji": "✈️",
        },
        {
            "title": "🩺 Annual Health Checkup Appointment",
            "media_url": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=800",
            "remind_time_iso": "2026-09-20T10:30:00+05:30",
            "reason": "Fast 8 hours prior to blood test. Bring previous medical history records.",
            "status": "Upcoming",
            "icon_emoji": "🩺",
        },
        {
            "title": "🎵 Live Concert Pass & Gate Ticket",
            "media_url": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=800",
            "remind_time_iso": "2026-09-10T18:00:00+05:30",
            "reason": "Show ticket QR code at Gate 4 before 7:00 PM.",
            "status": "Done",
            "icon_emoji": "🎵",
        },
    ]

    print(f"Adding {len(sample_reminders)} sample Essential Space entries to database {DATABASE_ID}...\n")
    for r in sample_reminders:
        try:
            create_reminder_entry(
                title=r["title"],
                media_url=r["media_url"],
                remind_time_iso=r["remind_time_iso"],
                reason=r["reason"],
                status=r["status"],
                icon_emoji=r["icon_emoji"],
            )
        except APIResponseError as e:
            print(f"❌ Failed to create {r['title']}: {e}")

    print("\n✓ Sample pages added successfully!")


if __name__ == "__main__":
    main()
