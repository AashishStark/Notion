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


def clear_page_children(page_id):
    """Deletes all existing child blocks on the root page."""
    print(f"Clearing existing content on page {page_id}...")
    has_more = True
    start_cursor = None
    deleted_count = 0

    while has_more:
        res = safe_api_call(
            client.blocks.children.list,
            block_id=page_id,
            start_cursor=start_cursor,
            page_size=100,
        )
        results = res.get("results", [])
        for block in results:
            safe_api_call(client.blocks.delete, block_id=block["id"])
            deleted_count += 1
            time.sleep(0.1)

        has_more = res.get("has_more", False)
        start_cursor = res.get("next_cursor")

    print(f"Cleared {deleted_count} existing blocks.")


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
    full = (title + " " + text_content).lower()

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
    """Calculates length in UTF-16 code units (as expected by Notion API)."""
    if not s:
        return 0
    return len(s.encode("utf-16-le")) // 2


def safe_chunk_text(text, max_utf16=1800):
    """Splits text into chunks strictly under max_utf16 code units."""
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


def build_blocks_for_note(note):
    blocks = []
    dt = note.get("date")
    if dt:
        blocks.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "🗓️"},
                    "color": "gray_background",
                    "rich_text": text_to_rich_text(
                        "Imported Keep Note • Created: " + str(dt)
                    ),
                },
            }
        )

    items = note.get("items", [])
    category = note.get("category", "")

    # Special formatting for sensitive credential notes
    if (
        "Credentials" in category
        or "🔐" in category
        or note["title"] in ["🔑", "🔑(1)"]
    ):
        code_lines = []
        for item in items:
            code_lines.append(item)
        full_code = "\n".join(code_lines) if code_lines else "No content"

        # Chunk code content safely into separate code blocks under 1800 UTF-16 code units
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
        blocks.append(toggle_block)
        return blocks

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
                blocks.append(
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
                blocks.append(
                    {
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": text_to_rich_text(clean)
                        },
                    }
                )
            else:
                blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": text_to_rich_text(line_str)
                        },
                    }
                )

    return blocks


def main():
    print("Loading notes.json...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    children = data.get("template", {}).get("children", [])
    print(f"Found {len(children)} child notes in notes.json.")

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

        # Build full searchable text representation
        clean_items = []
        for it in extracted_items:
            clean_it = (
                it.replace("☐\n", "[ ] ")
                .replace("☑\n", "[x] ")
                .replace("☐", "[ ]")
                .replace("☑", "[x]")
            )
            clean_items.append(clean_it)
        searchable_text = "\n".join(clean_items)

        parsed_notes.append(
            {
                "index": i,
                "title": raw_title,
                "category": cat,
                "icon": icon,
                "type": ntype,
                "date": date_str,
                "items": extracted_items,
                "searchable_content": searchable_text,
            }
        )

    # 1. Clear root page
    clear_page_children(ROOT_PAGE_ID)

    # 2. Add Welcome Banner & Layout Overview Callout
    print("Creating Header Banner Callout...")
    safe_api_call(
        client.blocks.children.append,
        block_id=ROOT_PAGE_ID,
        children=[
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "🗃️"},
                    "color": "blue_background",
                    "rich_text": text_to_rich_text(
                        "📌 **Google Keep Notes Workspace**\nAll 108 notes imported into a Master Database with Pinned Notes view, Global Full-Text Search index, and Category Board views."
                    ),
                },
            }
        ],
    )

    # 3. Create Master Database & Update Data Source Schema
    print("Creating Master Inline Database...")

    db = safe_api_call(
        client.databases.create,
        parent={"type": "page_id", "page_id": ROOT_PAGE_ID},
        title=[{"type": "text", "text": {"content": "🗂️ Keep Notes Database"}}],
        is_inline=True,
    )

    db_id = db["id"]
    ds_id = db.get("data_sources", [{}])[0].get("id")
    print(f"Created database with ID: {db_id} (Data Source ID: {ds_id})")

    print("Configuring Database Schema Properties...")
    db_properties = {
        "Name": {"title": {}},
        "📌 Pinned": {"checkbox": {}},
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
        "Searchable Content": {"rich_text": {}},
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

    # 4. Populate Database with all 108 Notes
    print("Populating Database Pages...")
    for i, note in enumerate(parsed_notes):
        print(
            f"[{i+1}/108] Creating note page: {note['title']} ({note['category']})"
        )

        blocks = build_blocks_for_note(note)

        initial_blocks = blocks[:100]
        remaining_blocks = blocks[100:]

        props = {
            "Name": text_to_rich_text(note["title"]),
            "📌 Pinned": False,
            "Category": {"name": note["category"]},
            "Note Type": {"name": note["type"]},
            "Searchable Content": text_to_rich_text(note["searchable_content"]),
        }

        if note["date"]:
            props["Original Date"] = {"start": note["date"]}

        page = safe_api_call(
            client.pages.create,
            parent={"database_id": db_id},
            icon={"type": "emoji", "emoji": note["icon"]},
            properties=props,
            children=initial_blocks,
        )

        if remaining_blocks:
            page_id = page["id"]
            for chunk_idx in range(0, len(remaining_blocks), 100):
                chunk = remaining_blocks[chunk_idx : chunk_idx + 100]
                safe_api_call(
                    client.blocks.children.append,
                    block_id=page_id,
                    children=chunk,
                )
                time.sleep(0.2)

        time.sleep(0.35)

    print(
        "\n✅ Successfully exported and formatted all 108 notes with Pinned Notes & Search Index in Notion!"
    )


if __name__ == "__main__":
    main()
