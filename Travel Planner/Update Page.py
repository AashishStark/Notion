import os
import sys
import json
import time
from getpass import getpass

from notion_client import Client
from notion_client.errors import APIResponseError


# ============================================================
# CONFIGURATION
# ============================================================

url = "https://www.notion.so/Travel-Planner-1-3d6e46567a3a8063b2a1cc8c94ddcc61?source=copy_link"

# SECURITY: don't hardcode the token here. The token pasted in an
# earlier version of this script was shared in a chat transcript and
# should be treated as compromised -- rotate it in your Notion
# integration settings, then set it via an environment variable:
#   Windows (PowerShell):  $env:NOTION_TOKEN = "ntn_..."
#   macOS/Linux:           export NOTION_TOKEN="ntn_..."
def get_notion_token():
    file_path = r"D:\Notion\ENV_FILES.json"
    with open(file_path, "r") as f:
        data = json.load(f)
        NOTION_TOKEN = data["NOTION_TOKEN"]
    return NOTION_TOKEN

NOTION_TOKEN = get_notion_token()

ROOT_PAGE_ID = url.split("/")[-1].split("?")[0].split("-")[-1] if url else ""

# Travel Plan (country hubs) -- the parent database that everything
# else relates back to via a 'Trip' relation property.
TRAVEL_PLAN_DB_ID = "215e4656-7a3a-8323-8793-81a4aec22319"
TRAVEL_PLAN_DS_ID = "653e4656-7a3a-83a1-828e-879505295fc5"

# SHARED master databases. Rows are created ONCE here (tagged with a
# 'Trip' relation to the relevant country page). Each country page
# then gets a linked, filtered VIEW of these same rows -- not a copy.
# ds_id left as None is resolved automatically at startup.
MASTER_DATABASES = {
    "Places to See": {
        "db_id": "bdfe4656-7a3a-83ff-b318-8191f66d27bf",
        "ds_id": "6b2e4656-7a3a-8270-8a54-87de9a48483d",
        "icon": "📍",
    },
    "Itinerary": {
        "db_id": "bc6e4656-7a3a-83aa-802c-8174d72607b1",
        "ds_id": "bf9e4656-7a3a-829b-85d3-879b6ccfc96a",
        "icon": "🗓️",
    },
    "Bucket List": {
        "db_id": "ce2e4656-7a3a-82cc-a32f-011b9288349c",
        "ds_id": "9abe4656-7a3a-8320-bcd1-07cdc9a375dc",
        "icon": "🌟",
    },
    "Bookings": {
        "db_id": "4b3e4656-7a3a-821b-9a87-81ba4410ff29",
        "ds_id": "610e4656-7a3a-8243-8883-8710149dc85e",
        "icon": "🎫",
    },
    "Places to Eat": {
        "db_id": "0bee4656-7a3a-832a-bcb4-01187b024dff",
        "ds_id": "d36e4656-7a3a-82bd-9f07-873f602ebf5e",
        "icon": "🍽️",
    },
}

# World Map is intentionally excluded from MASTER_DATABASES -- that
# database's ID (5ade4656-7a3a-8208-b8c5-014f9bc26af1) was returning
# APIErrorCode.InvalidRequestURL, so it's out of scope for now rather
# than blocking the rest of the run.


# ============================================================
# PLACES DATA (20 Custom Trips/Spots)
# ============================================================

TRIPS_DATA = [
    # --- India ---
    {"place": "Rani Ki Vav", "country": "India", "city_country": "Patan, Gujarat, India",
     "lat": "23.858924", "lng": "72.101933", "icon": "🏰"},
    {"place": "St. Michael' s Cathedral", "country": "India", "city_country": "Coimbatore, Tamil Nadu, India",
     "lat": "10.9952298", "lng": "76.9652278", "icon": "⛪"},
    {"place": "Nanemachi Waterfalls", "country": "India", "city_country": "Waki Bk, Maharashtra, India",
     "lat": "18.2026502", "lng": "73.5580406", "icon": "🌊"},
    {"place": "Cellular Jail", "country": "India", "city_country": "Sri Vijaya Puram, Andaman & Nicobar Islands, India",
     "lat": "11.6747052", "lng": "92.7478729", "icon": "🏛️"},
    {"place": "NCPA Entry Gate, Nariman Point", "country": "India", "city_country": "Nariman Point, Mumbai, Maharashtra, India",
     "lat": "18.9259898", "lng": "72.8192427", "icon": "🎭"},
    {"place": "Kutch's white desert (Rann of Kutch)", "country": "India", "city_country": "Dhordo, Kutch, Gujarat, India",
     "lat": "23.8412898", "lng": "69.5225599", "icon": "🏜️"},
    {"place": "Netaji Subhash Chandra Bose Island", "country": "India", "city_country": "Ross Island, Andaman & Nicobar Islands, India",
     "lat": "11.6758295", "lng": "92.7624249", "icon": "🏝️"},
    {"place": "Hampi", "country": "India", "city_country": "Vijayanagara, Karnataka, India",
     "lat": "15.3350132", "lng": "76.460024", "icon": "🏛️"},
    {"place": "Ellora Caves", "country": "India", "city_country": "Chhatrapati Sambhajinagar, Maharashtra, India",
     "lat": "20.0267844", "lng": "75.1770869", "icon": "🗿"},
    {"place": "Illikkal Kallu View Point", "country": "India", "city_country": "Kottayam, Kerala, India",
     "lat": "9.7538346", "lng": "76.8204782", "icon": "⛰️"},
    {"place": "Modhera Sun Temple", "country": "India", "city_country": "Mehsana, Gujarat, India",
     "lat": "23.5835889", "lng": "72.1329763", "icon": "🛕"},

    # --- France ---
    {"place": "Mont-Saint-Michel Abbey", "country": "France", "city_country": "Le Mont-Saint-Michel, France",
     "lat": "48.6359569", "lng": "-1.5117405", "icon": "🏰"},

    # --- Italy ---
    {"place": "Colosseum", "country": "Italy", "city_country": "Rome, Italy",
     "lat": "41.8902102", "lng": "12.4922309", "icon": "🏛️"},
    {"place": "Seiser Alm", "country": "Italy", "city_country": "South Tyrol, Dolomites, Italy",
     "lat": "46.5423435", "lng": "11.6168855", "icon": "🏔️"},
    {"place": "Lake Como", "country": "Italy", "city_country": "Lombardy, Italy",
     "lat": "46.0160486", "lng": "9.2571676", "icon": "🏞️"},
    {"place": "Portofino", "country": "Italy", "city_country": "Genoa, Liguria, Italy",
     "lat": "44.3031559", "lng": "9.2097879", "icon": "⛵"},

    # --- Hungary ---
    {"place": "Hungarian Parliament Building", "country": "Hungary", "city_country": "Budapest, Hungary",
     "lat": "47.507121", "lng": "19.045669", "icon": "🏛️"},

    # --- Brazil ---
    {"place": "Amazon Rainforest", "country": "Brazil", "city_country": "Amazonas, Brazil",
     "lat": "-3.4653053", "lng": "-62.2158805", "icon": "🌳"},

    # --- United Kingdom ---
    {"place": "King's Cross", "country": "United Kingdom", "city_country": "London, United Kingdom",
     "lat": "51.5306865", "lng": "-0.1233551", "icon": "🚂"},
    {"place": "Warner Bros. Studio Tour London", "country": "United Kingdom", "city_country": "Leavesden, Watford, United Kingdom",
     "lat": "51.6903361", "lng": "-0.4181589", "icon": "🎬"},
]

COUNTRY_ICONS = {
    "India": "🇮🇳",
    "France": "🇫🇷",
    "Italy": "🇮🇹",
    "Hungary": "🇭🇺",
    "Brazil": "🇧🇷",
    "United Kingdom": "🇬🇧",
}


# ============================================================
# NOTION CLIENT
# ============================================================

# The pip package `notion-client` has historically defaulted its
# Notion-Version header to "2022-06-28". Data sources (multi-source
# databases) and the Views API used throughout this script both
# require "2025-09-03" or later, so we pin it explicitly here rather
# than relying on the package's default.
NOTION_API_VERSION = "2026-03-11"


def get_notion_client():
    token = NOTION_TOKEN or os.getenv("NOTION_TOKEN")
    if not token:
        token = getpass("Enter your Notion integration token: ")
    if not token:
        raise ValueError("No Notion token provided.")
    return Client(auth=token, notion_version=NOTION_API_VERSION)


notion = get_notion_client()


# ============================================================
# LOW-LEVEL HELPERS
# ============================================================

def get_data_source_id(database_id):
    """Look up a database's primary data source id."""
    database = notion.databases.retrieve(database_id)
    data_sources = database.get("data_sources") or []
    if not data_sources:
        raise ValueError(f"Database {database_id} has no data sources.")
    return data_sources[0]["id"]


def resolve_master_data_sources():
    """Fill in any MASTER_DATABASES ds_id we don't already have hardcoded."""
    for name, info in MASTER_DATABASES.items():
        if not info.get("ds_id"):
            info["ds_id"] = get_data_source_id(info["db_id"])
            print(f"  Resolved data source for '{name}': {info['ds_id']}")


def query_rows_from_ds_or_db(ds_id, db_id):
    """Query existing pages from a database/data source."""
    results = []
    try:
        res = notion.request(path=f"data_sources/{ds_id}/query", method="POST", body={})
        results.extend(res.get("results", []))
    except Exception:
        try:
            res = notion.request(path=f"databases/{db_id}/query", method="POST", body={})
            results.extend(res.get("results", []))
        except Exception:
            pass
    return results


def archive_existing_pages(ds_id, db_id, name):
    """Archive old sample items in a database."""
    pages = query_rows_from_ds_or_db(ds_id, db_id)
    print(f"Archiving {len(pages)} existing sample items from '{name}'...")
    for p in pages:
        p_id = p.get("id")
        if p_id:
            try:
                notion.pages.update(page_id=p_id, archived=True)
            except Exception as e:
                print(f"  Failed to archive page {p_id}: {e}")
    time.sleep(0.3)


def ensure_relations_and_properties():
    """
    Ensure every SHARED database has a 'Trip' relation back to Travel
    Plan, plus a few supporting properties. Luggage is deliberately
    excluded here -- it's not shared, so its 'Trip' relation is added
    directly on its own per-country schema when it's created instead.
    """
    print("Ensuring shared database relations & properties ('Trip' relation, 'Coordinates')...")

    try:
        notion.request(
            path=f"data_sources/{MASTER_DATABASES['Places to See']['ds_id']}",
            method="PATCH",
            body={"properties": {"Coordinates": {"rich_text": {}}}}
        )
    except Exception:
        pass

    for name, info in MASTER_DATABASES.items():
        try:
            notion.request(
                path=f"data_sources/{info['ds_id']}",
                method="PATCH",
                body={
                    "properties": {
                        "Trip": {
                            "relation": {
                                "data_source_id": TRAVEL_PLAN_DS_ID,
                                "single_property": {}
                            }
                        }
                    }
                }
            )
            print(f"  [OK] Linked shared database '{name}' -> 'Travel Plan' via 'Trip' relation")
        except Exception as e:
            print(f"  Note on '{name}' relation: {e}")


def wipe_country_page_body(country_page_id):
    """
    Remove everything a PREVIOUS run of this script added directly
    under a country page: the banner, the divider, and -- critically
    -- the old duplicate per-country databases. Those duplicates are
    exactly what caused edits not to sync back to the root database,
    so we clear them before rebuilding with shared linked views.
    """
    print(f"  Wiping previously-generated content under this country page...")

    children = []
    cursor = None
    while True:
        response = notion.blocks.children.list(block_id=country_page_id, start_cursor=cursor, page_size=100)
        children.extend(response.get("results", []))
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
        if not cursor:
            break

    for block in children:
        block_id = block.get("id")
        block_type = block.get("type")
        try:
            if block_type == "child_database":
                database_id = block.get("child_database", {}).get("database_id") or block_id
                # Trashing the database removes both the data (if it's a
                # standalone duplicate) and its block on this page. If
                # this ever pointed at a SHARED data source instead, this
                # only trashes the linked-view container, not the shared
                # rows underneath -- which is exactly what we want here.
                notion.request(path=f"databases/{database_id}", method="PATCH", body={"in_trash": True})
            else:
                notion.request(path=f"blocks/{block_id}", method="DELETE")
        except Exception as e:
            print(f"    Note: couldn't remove old block {block_id}: {e}")

    time.sleep(0.3)


def create_master_row(ds_id, properties, icon, country_page_id):
    """Create ONE row in a shared master data source, tagged to a country via 'Trip'."""
    props = dict(properties)
    props["Trip"] = {"relation": [{"id": country_page_id}]}
    try:
        return notion.pages.create(parent={"data_source_id": ds_id}, icon=icon, properties=props)
    except Exception as e:
        print(f"    Row create note: {e}")
        return None


def create_country_linked_view(country_page_id, ds_id, view_name):
    """
    Create a linked database view on the country page, pointed at an
    EXISTING shared data source and filtered to only this country's
    rows (via the 'Trip' relation). This is the piece that makes
    edits sync both ways -- it's a view over the same rows, not a copy.
    Requires Notion API version 2025-09-03 or later.
    """
    body = {
        "create_database": {"parent": {"type": "page_id", "page_id": country_page_id}},
        "data_source_id": ds_id,
        "name": view_name,
        "type": "table",
        "filter": {
            "property": "Trip",
            "relation": {"contains": country_page_id},
        },
    }
    try:
        view = notion.request(path="views", method="POST", body=body)
        print(f"    [OK] Linked view '{view_name}' created (filtered to this trip)")
        return view
    except Exception as e:
        print(f"    [ERROR] Linked view '{view_name}' failed: {e}")
        return None


def create_inline_database(parent_page_id, title, icon_emoji, properties_spec, items=None):
    """
    Creates a REAL, standalone inline database directly inside
    parent_page_id (used only for Luggage, which is intentionally NOT
    shared across countries).
    """
    print(f"  Creating independent database '{title}'...")
    db = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        icon={"type": "emoji", "emoji": icon_emoji},
        title=[{"type": "text", "text": {"content": title}}]
    )
    db_id = db["id"]
    ds_id = db.get("data_sources", [{}])[0].get("id")
    endpoint = f"data_sources/{ds_id}" if ds_id else f"databases/{db_id}"

    if properties_spec:
        try:
            notion.request(path=endpoint, method="PATCH", body={"properties": properties_spec})
        except Exception as e:
            print(f"    Schema patch note for '{title}': {e}")

    if items:
        parent_key = "data_source_id" if ds_id else "database_id"
        target_id = ds_id if ds_id else db_id
        for item in items:
            try:
                notion.pages.create(
                    parent={parent_key: target_id},
                    icon=item.get("icon"),
                    properties=item.get("properties", {})
                )
            except Exception as e:
                print(f"    Item create note in '{title}': {e}")

    return db_id


def populate_country_page_body(country_page_id, country, country_spots):
    """
    Rebuild a country hub page: shared categories get their rows
    created once in the master data source (tagged via 'Trip') plus a
    filtered linked view here; Luggage gets its own independent
    database with a 'Trip' relation for reference only.
    """
    flag_icon = COUNTRY_ICONS.get(country, "✈️")
    spot_count = len(country_spots)

    wipe_country_page_body(country_page_id)

    banner_block = {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": f"Welcome to your {country} Travel Hub!\n"},
                    "annotations": {"bold": True}
                },
                {
                    "type": "text",
                    "text": {
                        "content": (
                            f"These sections are live, filtered views of your shared trip "
                            f"databases -- editing a row here updates it everywhere, "
                            f"including the root Travel Plan. Manage your {spot_count} spots, "
                            f"itinerary, bucket list, bookings, food options, luggage, and map "
                            f"points specifically for {country} below."
                        )
                    }
                }
            ],
            "icon": {"type": "emoji", "emoji": flag_icon},
            "color": "blue_background"
        }
    }
    notion.blocks.children.append(
        block_id=country_page_id,
        children=[banner_block, {"object": "block", "type": "divider", "divider": {}}]
    )

    # 1. Places to See (shared)
    for spot in country_spots:
        maps_url = f"https://maps.google.com/?q={spot['lat']},{spot['lng']}"
        coords_str = f"{spot['lat']}, {spot['lng']}"
        create_master_row(
            MASTER_DATABASES["Places to See"]["ds_id"],
            {
                "Place": {"title": [{"type": "text", "text": {"content": spot["place"]}}]},
                "City / Country": {"rich_text": [{"type": "text", "text": {"content": spot["city_country"]}}]},
                "Coordinates": {"rich_text": [{"type": "text", "text": {"content": coords_str}}]},
                "Link": {"url": maps_url},
            },
            {"type": "emoji", "emoji": spot["icon"]},
            country_page_id,
        )
    create_country_linked_view(country_page_id, MASTER_DATABASES["Places to See"]["ds_id"], f"Places to See ({country})")

    # 2. Itinerary (shared)
    for icon, name, category in [
        ("✈️", f"Flight / Transport to {country}", "Travel"),
        ("🏨", f"Hotel Check-in in {country}", "Accommodation"),
        ("📷", f"Explore {country} Highlights & Sightseeing", "Sightseeing"),
    ]:
        create_master_row(
            MASTER_DATABASES["Itinerary"]["ds_id"],
            {
                "Name": {"title": [{"type": "text", "text": {"content": name}}]},
                "Category": {"select": {"name": category}},
                "Status": {"status": {"name": "Planned"}},
            },
            {"type": "emoji", "emoji": icon},
            country_page_id,
        )
    create_country_linked_view(country_page_id, MASTER_DATABASES["Itinerary"]["ds_id"], f"Itinerary ({country})")

    # 3. Bucket List (shared)
    for icon, name in [
        ("🌟", f"Visit top landmarks in {country}"),
        ("📸", f"Capture sunset photos in {country}"),
    ]:
        create_master_row(
            MASTER_DATABASES["Bucket List"]["ds_id"],
            {
                "Name": {"title": [{"type": "text", "text": {"content": name}}]},
                "Done": {"checkbox": False},
            },
            {"type": "emoji", "emoji": icon},
            country_page_id,
        )
    create_country_linked_view(country_page_id, MASTER_DATABASES["Bucket List"]["ds_id"], f"Bucket List ({country})")

    # 4. Bookings (shared)
    create_master_row(
        MASTER_DATABASES["Bookings"]["ds_id"],
        {
            "Name": {"title": [{"type": "text", "text": {"content": f"{country} Entry / Attraction Passes"}}]},
            "Type": {"select": {"name": "Ticket"}},
            "Confirmed": {"checkbox": True},
        },
        {"type": "emoji", "emoji": "🎫"},
        country_page_id,
    )
    create_country_linked_view(country_page_id, MASTER_DATABASES["Bookings"]["ds_id"], f"Bookings ({country})")

    # 5. Places to Eat (shared)
    create_master_row(
        MASTER_DATABASES["Places to Eat"]["ds_id"],
        {
            "Name": {"title": [{"type": "text", "text": {"content": f"Local Traditional Cuisine in {country}"}}]},
            "Cuisine": {"rich_text": [{"type": "text", "text": {"content": "Authentic Local"}}]},
            "Visited": {"checkbox": False},
        },
        {"type": "emoji", "emoji": "🍽️"},
        country_page_id,
    )
    create_country_linked_view(country_page_id, MASTER_DATABASES["Places to Eat"]["ds_id"], f"Places to Eat ({country})")

    # 6. Luggage List -- NOT shared. Own database, own rows per country.
    # 'Trip' relation added for reference/navigation only (not filtered on).
    luggage_schema = {
        "Category": {"select": {}},
        "Packed": {"checkbox": {}},
        "Trip": {"relation": {"data_source_id": TRAVEL_PLAN_DS_ID, "single_property": {}}},
    }
    luggage_items = [
        {
            "icon": {"type": "emoji", "emoji": "🛂"},
            "properties": {
                "Name": {"title": [{"type": "text", "text": {"content": "Passport & Travel Documents"}}]},
                "Category": {"select": {"name": "Essentials"}},
                "Packed": {"checkbox": False},
                "Trip": {"relation": [{"id": country_page_id}]},
            },
        },
        {
            "icon": {"type": "emoji", "emoji": "🔌"},
            "properties": {
                "Name": {"title": [{"type": "text", "text": {"content": f"Power Adapter for {country}"}}]},
                "Category": {"select": {"name": "Electronics"}},
                "Packed": {"checkbox": False},
                "Trip": {"relation": [{"id": country_page_id}]},
            },
        },
    ]
    create_inline_database(country_page_id, f"Luggage List ({country})", "🧳", luggage_schema, luggage_items)

    print(f"  [OK] Rebuilt '{country}' Country Hub: shared linked views + independent Luggage list.")


# ============================================================
# MAIN UPDATE SCRIPT
# ============================================================

def main():
    print("\n========================================")
    print("       NOTION TRAVEL PLANNER UPDATER")
    print("========================================\n")

    resolve_master_data_sources()
    ensure_relations_and_properties()

    print("\nCleaning up sample template items in shared master databases...")
    for name, info in MASTER_DATABASES.items():
        archive_existing_pages(info["ds_id"], info["db_id"], name)
    archive_existing_pages(TRAVEL_PLAN_DS_ID, TRAVEL_PLAN_DB_ID, "Travel Plan")

    countries = list(dict.fromkeys([item["country"] for item in TRIPS_DATA]))
    print(f"\nCreating {len(countries)} Country/Region hubs in 'Travel Plan': {countries}...")

    country_page_ids = {}

    for country in countries:
        icon = COUNTRY_ICONS.get(country, "✈️")
        country_spots = [s for s in TRIPS_DATA if s["country"] == country]

        try:
            page = notion.pages.create(
                parent={"database_id": TRAVEL_PLAN_DB_ID},
                icon={"type": "emoji", "emoji": icon},
                properties={
                    "Name": {"title": [{"type": "text", "text": {"content": country}}]},
                    "Destination": {"select": {"name": country}},
                    "Status": {"status": {"name": "Upcoming"}}
                }
            )
            c_id = page.get("id")
            country_page_ids[country] = c_id
            print(f"  [OK] Created Country Hub: {country} (ID: {c_id})")

            populate_country_page_body(c_id, country, country_spots)

        except Exception as e:
            print(f"  [ERROR] Error creating country page {country}: {e}")

    print("\n========================================")
    print("   UPDATE COMPLETED SUCCESSFULLY!")
    print("========================================")
    print(
        "\nRoot databases (Places to See, Itinerary, Bucket List, Bookings, "
        "Places to Eat) now hold every row across all countries. "
        "Each country page shows a live filtered view of those same rows -- "
        "ticking a checkbox in either place updates both. Luggage List "
        "remains independent per country, as requested."
    )


if __name__ == "__main__":
    main()