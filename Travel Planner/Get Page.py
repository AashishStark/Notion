import json
import os
import re
import time
from getpass import getpass

from notion_client import Client
from notion_client.errors import APIResponseError


# ============================================================
# CONFIGURATION
# ============================================================

url = "https://www.notion.so/Travel-Planner-1-3d6e46567a3a8063b2a1cc8c94ddcc61?source=copy_link"


def get_notion_token():
    file_path = r"D:\Notion\ENV_FILES.json"
    with open(file_path, "r") as f:
        data = json.load(f)
        NOTION_TOKEN = data["NOTION_TOKEN"]
    return NOTION_TOKEN

NOTION_TOKEN = get_notion_token()

ROOT_PAGE_ID = url.split("/")[-1].split("?")[0].split("-")[-1] if url else ""

# Output file
OUTPUT_FILE = r"D:\Notion\Travel Planner\travel_planner.json"

# Set to True if you want raw Notion API responses included in JSON.
INCLUDE_RAW_API = True

# Regex for matching Notion 32-hex IDs (with or without hyphens)
NOTION_ID_REGEX = re.compile(
    r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}",
    re.IGNORECASE,
)


# ============================================================
# NOTION CLIENT & VISITED TRACKER
# ============================================================

def get_notion_client():
    """Get the Notion integration token."""
    token = NOTION_TOKEN or os.getenv("NOTION_TOKEN")

    if not token:
        token = getpass("Enter your Notion integration token: ")

    if not token:
        raise ValueError("No Notion token provided.")

    return Client(auth=token)


notion = get_notion_client()

# Set of normalized IDs to prevent circular loops / duplicate processing
_visited_pages = set()
_visited_databases = set()


# ============================================================
# HELPERS
# ============================================================

def clean_id(value):
    """Convert Notion IDs to string representation."""
    if value is None:
        return None
    return str(value)


def normalize_id(value):
    """Convert Notion ID to 32-character lowercase hex string without hyphens for reliable comparison."""
    if not value:
        return ""
    return str(value).replace("-", "").lower()


def rich_text_to_text(rich_text):
    """Convert Notion rich_text objects into plain text."""
    if not rich_text:
        return ""
    result = []
    for item in rich_text:
        plain_text = item.get("plain_text")
        if plain_text:
            result.append(plain_text)
    return "".join(result)


def extract_rich_text(rich_text):
    """Preserve useful information from a Notion rich_text object."""
    result = []
    for item in rich_text or []:
        entry = {
            "plain_text": item.get("plain_text"),
            "href": item.get("href"),
            "annotations": item.get("annotations"),
            "type": item.get("type"),
        }
        item_type = item.get("type")
        if item_type in item:
            entry[item_type] = item[item_type]
        result.append(entry)
    return result


def extract_title_from_property(property_data):
    """Extract readable title from a Notion title property."""
    if not property_data:
        return ""
    title = property_data.get("title", [])
    return rich_text_to_text(title)


def extract_property_value(property_data):
    """Convert a Notion property value into a simpler, machine-readable form."""
    if not property_data:
        return None

    property_type = property_data.get("type")
    if not property_type:
        return property_data

    value = property_data.get(property_type)

    if property_type in ("title", "rich_text"):
        return {
            "type": property_type,
            "text": rich_text_to_text(value) if isinstance(value, list) else value,
            "rich_text": extract_rich_text(value) if isinstance(value, list) else None,
        }

    if property_type == "select":
        if value is None:
            return None
        return {"type": "select", "name": value.get("name"), "id": value.get("id"), "color": value.get("color")}

    if property_type == "multi_select":
        return {
            "type": "multi_select",
            "options": [
                {"name": o.get("name"), "id": o.get("id"), "color": o.get("color")}
                for o in (value or [])
            ],
        }

    if property_type == "status":
        if value is None:
            return None
        return {"type": "status", "name": value.get("name"), "id": value.get("id"), "color": value.get("color")}

    if property_type == "date":
        if value is None:
            return None
        return {"type": "date", "start": value.get("start"), "end": value.get("end"), "time_zone": value.get("time_zone")}

    if property_type == "checkbox":
        return {"type": "checkbox", "value": value}

    if property_type == "number":
        return {"type": "number", "value": value}

    if property_type == "url":
        return {"type": "url", "value": value}

    if property_type == "email":
        return {"type": "email", "value": value}

    if property_type == "phone_number":
        return {"type": "phone_number", "value": value}

    if property_type == "people":
        return {
            "type": "people",
            "people": [{"id": p.get("id"), "type": p.get("type")} for p in (value or [])],
        }

    if property_type == "files":
        return {"type": "files", "files": value}

    if property_type == "relation":
        return {"type": "relation", "relations": [{"id": r.get("id")} for r in (value or [])]}

    if property_type == "formula":
        return {"type": "formula", "value": value}

    if property_type == "rollup":
        return {"type": "rollup", "value": value}

    if property_type in ("created_time", "created_by", "last_edited_time", "last_edited_by"):
        return {"type": property_type, "value": value}

    return {"type": property_type, "value": value}


def extract_mentions_and_links(block):
    """Extract page and database IDs embedded in block rich text, captions, or href links."""
    page_ids = set()
    db_ids = set()

    block_type = block.get("type")
    if not block_type or block_type not in block:
        return page_ids, db_ids

    content = block[block_type]
    if not isinstance(content, dict):
        return page_ids, db_ids

    rich_texts = []
    if "rich_text" in content and isinstance(content["rich_text"], list):
        rich_texts.extend(content["rich_text"])
    if "caption" in content and isinstance(content["caption"], list):
        rich_texts.extend(content["caption"])

    for item in rich_texts:
        if item.get("type") == "mention":
            mention = item.get("mention", {})
            m_type = mention.get("type")
            if m_type == "page" and mention.get("page", {}).get("id"):
                page_ids.add(mention["page"]["id"])
            elif m_type == "database" and mention.get("database", {}).get("id"):
                db_ids.add(mention["database"]["id"])

        href = item.get("href")
        if href and "notion.so" in href:
            matches = NOTION_ID_REGEX.findall(href)
            for m in matches:
                page_ids.add(m)

    url_val = content.get("url")
    if url_val and "notion.so" in url_val:
        matches = NOTION_ID_REGEX.findall(url_val)
        for m in matches:
            page_ids.add(m)

    return page_ids, db_ids


# ============================================================
# DATABASE QUERYING & INSPECTION
# ============================================================

def query_all_database_pages(database):
    """
    Query ALL rows/pages inside a Notion database using pagination.
    Supports both newer Notion API multi-source databases (via data_sources)
    and legacy single-source databases, handling linked database views gracefully.
    """
    results = []
    database_id = database.get("id") or database.get("database_id")
    data_sources = database.get("data_sources", [])

    # Case 1: Newer Notion API with data_sources
    if data_sources and isinstance(data_sources, list):
        for ds in data_sources:
            ds_id = ds.get("id")
            if not ds_id:
                continue

            cursor = None
            while True:
                try:
                    body = {"page_size": 100}
                    if cursor:
                        body["start_cursor"] = cursor

                    if hasattr(notion, "data_sources") and hasattr(notion.data_sources, "query"):
                        response = notion.data_sources.query(data_source_id=ds_id, **body)
                    else:
                        response = notion.request(
                            path=f"data_sources/{ds_id}/query",
                            method="POST",
                            body=body,
                        )
                    results.extend(response.get("results", []))

                    if not response.get("has_more"):
                        break

                    cursor = response.get("next_cursor")
                    if not cursor:
                        break

                    time.sleep(0.1)
                except Exception:
                    break

    # Case 2: Legacy single-source database querying / Linked database view fallback
    else:
        cursor = None
        while True:
            try:
                body = {"page_size": 100}
                if cursor:
                    body["start_cursor"] = cursor

                if hasattr(notion, "databases") and hasattr(notion.databases, "query"):
                    response = notion.databases.query(database_id=database_id, **body)
                else:
                    response = notion.request(
                        path=f"databases/{database_id}/query",
                        method="POST",
                        body=body,
                    )
                results.extend(response.get("results", []))

                if not response.get("has_more"):
                    break

                cursor = response.get("next_cursor")
                if not cursor:
                    break

                time.sleep(0.1)
            except Exception:
                # Linked database views or unqueryable database blocks fail gracefully
                break

    return results


def inspect_database(database_id, depth=0):
    """
    Inspect a Notion database: its schema AND every row/card inside it.
    """
    clean_db_id = clean_id(database_id)
    norm_id = normalize_id(database_id)

    if norm_id in _visited_databases:
        return {
            "database_id": clean_db_id,
            "type": "database",
            "_ref": True,
            "note": "Already inspected elsewhere in this document.",
        }

    _visited_databases.add(norm_id)

    print("  " * depth + f"Inspecting database: {clean_db_id}")

    result = {
        "database_id": clean_db_id,
        "type": "database",
        "properties": {},
        "rows": [],
    }

    try:
        database = notion.databases.retrieve(database_id=database_id)

        result["title"] = rich_text_to_text(database.get("title", []))
        result["url"] = database.get("url")
        result["description"] = rich_text_to_text(database.get("description", []))

        properties = database.get("properties", {})
        for name, prop in properties.items():
            property_info = {"id": prop.get("id"), "type": prop.get("type")}
            prop_type = prop.get("type")
            if prop_type in prop:
                property_info["config"] = prop[prop_type]
            result["properties"][name] = property_info

        # --- Traverse and inspect every row/page in the database ---
        raw_pages = query_all_database_pages(database)
        print("  " * depth + f"  -> Found {len(raw_pages)} entries in database '{result.get('title', 'Untitled')}'")

        for row in raw_pages:
            r_id = row.get("id")
            if r_id:
                inspected_page = inspect_page(r_id, depth + 1)
                result["rows"].append(inspected_page)

        if INCLUDE_RAW_API:
            result["_raw"] = database

    except APIResponseError as e:
        result["error"] = str(e)

    return result


# ============================================================
# BLOCK INSPECTION & WALKERS
# ============================================================

def inspect_block(block):
    """Convert one Notion block into a clean JSON object."""
    block_type = block.get("type")

    result = {
        "id": clean_id(block.get("id")),
        "type": block_type,
        "object": block.get("object"),
        "has_children": block.get("has_children", False),
    }

    for key in ("created_time", "last_edited_time", "archived", "in_trash"):
        if key in block:
            result[key] = block[key]

    if block_type in block:
        content = block[block_type]
        result["content"] = {}

        if isinstance(content, dict):
            if "rich_text" in content:
                result["content"]["text"] = rich_text_to_text(content["rich_text"])
                result["content"]["rich_text"] = extract_rich_text(content["rich_text"])

            if "caption" in content:
                result["content"]["caption"] = rich_text_to_text(content["caption"])

            for key in (
                "url", "external", "file", "expression", "language",
                "checked", "color", "synced_from", "table_width",
                "has_column_header", "has_row_header", "number_of_columns",
            ):
                if key in content:
                    result["content"][key] = content[key]

            if "database_id" in content:
                result["content"]["database_id"] = clean_id(content["database_id"])

            if "page_id" in content:
                result["content"]["page_id"] = clean_id(content["page_id"])

            known = {
                "rich_text", "caption", "url", "external", "file", "expression",
                "language", "checked", "color", "database_id", "page_id",
                "synced_from", "table_width", "has_column_header",
                "has_row_header", "number_of_columns",
            }
            result["content"]["other"] = {k: v for k, v in content.items() if k not in known}

        else:
            result["content"]["value"] = content

    if INCLUDE_RAW_API:
        result["_raw"] = block

    return result


def list_all_children(block_id):
    """Retrieve ALL child blocks, including pagination."""
    results = []
    cursor = None

    while True:
        response = notion.blocks.children.list(
            block_id=block_id,
            start_cursor=cursor,
            page_size=100,
        )
        results.extend(response.get("results", []))

        if not response.get("has_more"):
            break

        cursor = response.get("next_cursor")
        if not cursor:
            break

        time.sleep(0.1)

    return results


def inspect_children(parent_id, depth=0):
    """Recursively inspect every child block, database, and page."""
    blocks = []
    children = list_all_children(parent_id)

    for block in children:
        block_info = inspect_block(block)
        block_type = block.get("type")
        block_id = block.get("id")

        # ----------------------------------------------------
        # Child Database
        # Note: Notion API child_database block["id"] IS the database ID!
        # ----------------------------------------------------
        if block_type == "child_database":
            database_id = block_id or block.get("child_database", {}).get("database_id")
            if database_id and normalize_id(database_id) not in _visited_databases:
                block_info["database"] = inspect_database(database_id, depth + 1)

        # ----------------------------------------------------
        # Child Page
        # Note: Notion API child_page block["id"] IS the page ID!
        # ----------------------------------------------------
        if block_type == "child_page":
            page_id = block_id or block.get("child_page", {}).get("page_id")
            if page_id and normalize_id(page_id) not in _visited_pages:
                block_info["page"] = inspect_page(page_id, depth + 1)

        # ----------------------------------------------------
        # Link to Page / Linked Database
        # ----------------------------------------------------
        if block_type == "link_to_page":
            link_info = block.get("link_to_page", {})
            t_type = link_info.get("type")
            if t_type == "page_id" and link_info.get("page_id"):
                p_id = link_info["page_id"]
                if normalize_id(p_id) not in _visited_pages:
                    block_info["linked_page"] = inspect_page(p_id, depth + 1)
            elif t_type == "database_id" and link_info.get("database_id"):
                d_id = link_info["database_id"]
                if normalize_id(d_id) not in _visited_databases:
                    block_info["linked_database"] = inspect_database(d_id, depth + 1)

        # ----------------------------------------------------
        # Extract Page/Database Mentions & Links in Rich Text
        # ----------------------------------------------------
        linked_pages, linked_dbs = extract_mentions_and_links(block)
        if linked_pages:
            block_info["mentioned_pages"] = []
            for lp_id in linked_pages:
                if normalize_id(lp_id) not in _visited_pages:
                    block_info["mentioned_pages"].append(inspect_page(lp_id, depth + 1))

        if linked_dbs:
            block_info["mentioned_databases"] = []
            for ldb_id in linked_dbs:
                if normalize_id(ldb_id) not in _visited_databases:
                    block_info["mentioned_databases"].append(inspect_database(ldb_id, depth + 1))

        # ----------------------------------------------------
        # Nested block structure
        # ----------------------------------------------------
        if block.get("has_children", False) and block_type not in ("child_database", "child_page"):
            try:
                block_info["children"] = inspect_children(block["id"], depth + 1)
            except APIResponseError as e:
                block_info["children_error"] = str(e)

        blocks.append(block_info)

    return blocks


# ============================================================
# PAGE INSPECTION
# ============================================================

def inspect_page(page_id, depth=0):
    """Inspect one Notion page and everything underneath it."""
    clean_p_id = clean_id(page_id)
    norm_id = normalize_id(page_id)

    if norm_id in _visited_pages:
        return {
            "id": clean_p_id,
            "type": "page",
            "_ref": True,
            "note": "Already inspected elsewhere in this document.",
        }

    _visited_pages.add(norm_id)

    print("  " * depth + f"Inspecting page: {clean_p_id}")

    result = {"id": clean_p_id, "type": "page"}

    try:
        page = notion.pages.retrieve(page_id=page_id)

        result["url"] = page.get("url")
        result["created_time"] = page.get("created_time")
        result["last_edited_time"] = page.get("last_edited_time")
        result["archived"] = page.get("archived")
        result["in_trash"] = page.get("in_trash")
        result["icon"] = page.get("icon")
        result["cover"] = page.get("cover")
        result["parent"] = page.get("parent")

        result["properties"] = {}
        title = ""

        for name, prop in page.get("properties", {}).items():
            result["properties"][name] = {
                "id": prop.get("id"),
                "type": prop.get("type"),
                "value": extract_property_value(prop),
            }
            if prop.get("type") == "title":
                title = extract_title_from_property(prop)

        result["title"] = title

        result["children"] = inspect_children(page_id, depth + 1)

        if INCLUDE_RAW_API:
            result["_raw"] = page

    except APIResponseError as e:
        result["error"] = str(e)

    return result


# ============================================================
# CONNECTION TEST
# ============================================================

def test_connection():
    """Verify that the token works."""
    print("Testing Notion connection...")

    try:
        me = notion.users.me()
        print("Connected successfully.")
        print("Integration:", me.get("name") or me.get("bot", {}).get("owner"))
        return True
    except APIResponseError as e:
        print("Notion connection failed:")
        print(e)
        return False


# ============================================================
# MAIN
# ============================================================

def main():
    if not ROOT_PAGE_ID:
        print("\nERROR:")
        print("Set `url` at the top of the script to your template page's URL (or set ROOT_PAGE_ID directly).")
        print('\nExample:\nurl = "https://www.notion.so/My-Template-3d6e46567a3a8095a301c71623358b21"')
        return

    print("\n========================================")
    print("       NOTION TEMPLATE INSPECTOR")
    print("========================================\n")

    if not test_connection():
        return

    print("\nStarting recursive inspection (pages, blocks, database rows, links)...\n")

    _visited_pages.clear()
    _visited_databases.clear()

    template = inspect_page(ROOT_PAGE_ID)

    output = {
        "inspector": {
            "version": "2.0",
            "description": (
                "Recursive machine-readable snapshot of a Notion page, "
                "including rows inside nested databases and linked pages."
            ),
            "root_page_id": ROOT_PAGE_ID,
            "include_raw_api": INCLUDE_RAW_API,
        },
        "template": template,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print("\n========================================")
    print("Inspection completed.")
    print("========================================")
    print(f"\nSaved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
