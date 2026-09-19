import os
import sys
import json
import time
import re
import dateutil.parser
from notion_client import Client
from notion_client.errors import APIResponseError

# Set stdout encoding for Windows terminal unicode support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# ============================================================
# CONFIGURATION
# ============================================================

ROOT_PAGE_ID = "3dbe4656-7a3a-80d8-9907-eb65e73cd8b9"
INPUT_FILE = r"D:\Notion\Notes\notes.json"


def get_notion_token():
    file_path = r"D:\Notion\ENV_FILES.json"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data["NOTION_TOKEN"]


NOTION_TOKEN = get_notion_token()
client = Client(auth=NOTION_TOKEN)

# ============================================================
# HELPER FUNCTIONS
# ============================================================


def safe_api_call(func, *args, **kwargs):
    """Executes Notion API calls with retries for rate limits or temporary errors."""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except APIResponseError as e:
            if e.status in (429, 500, 502, 503, 504):
                wait = (attempt + 1) * 2
                print(f"API Rate limit / Error {e.status}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise e
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(1)


def parse_date(text):
    if not text:
        return None
    cleaned = text.replace("\u202f", " ").strip()
    try:
        dt = dateutil.parser.parse(cleaned, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def detect_category_and_icon(title, text_content):
    t = title.lower()

    if any(
        k in t
        for k in [
            "trip",
            "jibhi",
            "ooty",
            "munnar",
            "wayanad",
            "yercaud",
            "varkala",
            "places",
            "mumbai",
            "goa",
            "delhi",
        ]
    ):
        return "✈️ Travel & Trips", "✈️", "Trip Plan"
    elif any(
        k in t
        for k in ["movie", "book", "series", "shorts", "lyrics", "theatre"]
    ):
        return "🎬 Media & Books", "🎬", "Media List"
    elif any(
        k in t
        for k in [
            "🔑",
            "pass",
            "key",
            "email",
            "netflix",
            "acc",
            "credentials",
            "login",
        ]
    ):
        return "🔐 Credentials & Sensitive", "🔐", "Password / Key"
    elif any(
        k in t
        for k in ["to-do", "todo", "list", "check", "vaanga", "buying", "item"]
    ):
        return "📝 To-Dos & Checklists", "📝", "Checklist"
    elif (
        any(
            k in t
            for k in [
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
                "sat",
                "sun",
                "july",
                "aug",
                "sep",
                "oct",
                "nov",
                "dec",
                "2024-",
                "2025-",
                "2026-",
            ]
        )
        or re.match(r"^\d+\s+[a-zA-Z]+", t)
    ):
        return "🗓️ Daily Logs & Journals", "🗓️", "Daily Log"
    elif any(
        k in t
        for k in [
            "course",
            "embed",
            "deployment",
            "appviewx",
            "resume",
            "studies",
            "java",
            "slack",
        ]
    ):
        return "💼 Work & Learning", "💼", "Standard Note"
    elif any(
        k in t
        for k in [
            "quote",
            "love",
            "nightmare",
            "memorable",
            "story",
            "stanza",
            "thought",
            "tea",
        ]
    ):
        return "💡 Personal & Ideas", "💡", "Standard Note"
    else:
        return "📦 General & Misc", "📌", "Standard Note"


def utf16_len(s):
    if not s:
        return 0
    return len(s.encode("utf-16-le")) // 2


def safe_chunk_text(text, max_utf16=1800):
    if not text:
        return []
    chunks = []
    current = []
    current_utf16 = 0

    lines = text.split("\n")
    for line in lines:
        l_utf16 = utf16_len(line) + 1
        if l_utf16 > max_utf16:
            if current:
                chunks.append("\n".join(current))
                current = []
                current_utf16 = 0
            sub_chars = []
            sub_utf16 = 0
            for char in line:
                c_utf16 = utf16_len(char)
                if sub_utf16 + c_utf16 > max_utf16:
                    chunks.append("".join(sub_chars))
                    sub_chars = [char]
                    sub_utf16 = c_utf16
                else:
                    sub_chars.append(char)
                    sub_utf16 += c_utf16
            if sub_chars:
                chunks.append("".join(sub_chars))
        elif current_utf16 + l_utf16 > max_utf16:
            chunks.append("\n".join(current))
            current = [line]
            current_utf16 = l_utf16
        else:
            current.append(line)
            current_utf16 += l_utf16

    if current:
        chunks.append("\n".join(current))
    return chunks


def text_to_rich_text(text):
    if not text:
        return []
    chunks = safe_chunk_text(text, max_utf16=1800)
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks]


def build_synced_content_blocks(items, category, title):
    """Builds content blocks wrapped inside a Notion synced_block."""
    inner_blocks = []

    if (
        "Credentials" in category
        or "🔐" in category
        or title in ["🔑", "🔑(1)"]
    ):
        code_lines = [item for item in items]
        full_code = "\n".join(code_lines) if code_lines else "No content"

        code_chunks = safe_chunk_text(full_code, max_utf16=1800)
        child_code_blocks = []
        for chunk in code_chunks:
            child_code_blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [
                            {"type": "text", "text": {"content": chunk}}
                        ],
                    },
                }
            )

        toggle_block = {
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": text_to_rich_text(
                    "🔒 Sensitive Credentials (Click to Expand)"
                ),
                "color": "red_background",
                "children": child_code_blocks,
            },
        }
        inner_blocks.append(toggle_block)
    else:
        for item in items:
            norm = item.replace("☐\n", "☐ ").replace("☑\n", "☑ ")
            lines = norm.split("\n")
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue

                if line_str.startswith("☐") or line_str.startswith("☑"):
                    checked = line_str.startswith("☑")
                    clean = line_str[1:].strip()
                    if not clean:
                        continue
                    inner_blocks.append(
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": text_to_rich_text(clean),
                                "checked": checked,
                            },
                        }
                    )
                elif line_str.startswith("- ") or line_str.startswith("• "):
                    clean = line_str[2:].strip()
                    if not clean:
                        continue
                    inner_blocks.append(
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": text_to_rich_text(clean)
                            },
                        }
                    )
                else:
                    inner_blocks.append(
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": text_to_rich_text(line_str)
                            },
                        }
                    )

    synced_container = {
        "object": "block",
        "type": "synced_block",
        "synced_block": {
            "synced_from": None,
            "children": inner_blocks[:100],
        },
    }
    return synced_container


def main():
    print("Loading notes.json...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    children = data.get("template", {}).get("children", [])
    print(f"Found {len(children)} notes in notes.json.")

    parsed_notes = []
    for i, child in enumerate(children):
        page = child.get("page", {})
        raw_title = page.get("title", "").strip() or f"Untitled Note {i+1}"
        p_children = page.get("children", [])

        date_str = None
        extracted_items = []

        for idx, pc in enumerate(p_children):
            c_dict = pc.get("content", {})
            t = c_dict.get("text", "") or ""

            if idx == 0 and not date_str:
                d = parse_date(t)
                if d:
                    date_str = d
                    continue

            if t.strip() == raw_title:
                continue

            extracted_items.append(t)

        full_text = "\n".join(extracted_items)
        cat, icon, ntype = detect_category_and_icon(raw_title, full_text)

        if "☐" in full_text or "☑" in full_text:
            ntype = "Checklist"

        parsed_notes.append(
            {
                "index": i,
                "title": raw_title,
                "category": cat,
                "icon": icon,
                "type": ntype,
                "date": date_str,
                "items": extracted_items,
            }
        )

    # 1. Add Search Callout Banner (non-destructive append)
    print("Adding Search Mapping Callout Banner to Root Page...")
    safe_api_call(
        client.blocks.children.append,
        block_id=ROOT_PAGE_ID,
        children=[
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "🔍"},
                    "color": "yellow_background",
                    "rich_text": text_to_rich_text(
                        "🔍 **Content Search & Mapping Index**\nEvery note is mapped to a dedicated Synced Block. Edits typed inside the synced blocks update live across notes and search index."
                    ),
                },
            }
        ],
    )

    # 2. Create Search Database
    print("Creating New Inline Search Database...")
    db = safe_api_call(
        client.databases.create,
        parent={"type": "page_id", "page_id": ROOT_PAGE_ID},
        title=[
            {
                "type": "text",
                "text": {"content": "🔍 Content Search & Mapping Index"},
            }
        ],
        is_inline=True,
    )

    db_id = db["id"]
    ds_id = db.get("data_sources", [{}])[0].get("id")
    print(f"Created Search Database ID: {db_id} (Data Source ID: {ds_id})")

    db_properties = {
        "Name": {"title": {}},
        "Category": {
            "select": {
                "options": [
                    {"name": "✈️ Travel & Trips", "color": "blue"},
                    {"name": "🎬 Media & Books", "color": "purple"},
                    {"name": "🗓️ Daily Logs & Journals", "color": "orange"},
                    {"name": "🔐 Credentials & Sensitive", "color": "red"},
                    {"name": "📝 To-Dos & Checklists", "color": "green"},
                    {"name": "💡 Personal & Ideas", "color": "yellow"},
                    {"name": "💼 Work & Learning", "color": "pink"},
                    {"name": "📦 General & Misc", "color": "gray"},
                ]
            }
        },
        "Note Type": {
            "select": {
                "options": [
                    {"name": "Checklist", "color": "green"},
                    {"name": "Password / Key", "color": "red"},
                    {"name": "Daily Log", "color": "orange"},
                    {"name": "Trip Plan", "color": "blue"},
                    {"name": "Media List", "color": "purple"},
                    {"name": "Standard Note", "color": "default"},
                ]
            }
        },
        "Original Date": {"date": {}},
    }

    if ds_id:
        safe_api_call(
            client.data_sources.update,
            data_source_id=ds_id,
            properties=db_properties,
        )
    else:
        safe_api_call(
            client.databases.update, database_id=db_id, properties=db_properties
        )

    # 3. Populate Search Database Pages with Synced Blocks
    print("Populating Search Index Pages with Synced Blocks...")
    for i, note in enumerate(parsed_notes):
        print(
            f"[{i+1}/108] Indexing note: {note['title']} ({note['category']})"
        )

        synced_block = build_synced_content_blocks(
            note["items"], note["category"], note["title"]
        )

        props = {
            "Name": text_to_rich_text(note["title"]),
            "Category": {"name": note["category"]},
            "Note Type": {"name": note["type"]},
        }

        if note["date"]:
            props["Original Date"] = {"start": note["date"]}

        search_page = safe_api_call(
            client.pages.create,
            parent={"database_id": db_id},
            icon={"type": "emoji", "emoji": note["icon"]},
            properties=props,
            children=[synced_block],
        )

        time.sleep(0.35)

    print(
        "\n✅ Successfully created Search Database with Synced Blocks for all 108 notes!"
    )


if __name__ == "__main__":
    main()
