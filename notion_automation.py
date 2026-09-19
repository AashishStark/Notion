from notion_client import Client
from notion_client.errors import APIResponseError
import json
# ============================================================
# CONFIGURATION
# ============================================================
def get_notion_token():
    file_path = r"D:\Notion\ENV_FILES.json"
    with open(file_path, "r") as f:
        data = json.load(f)
        NOTION_TOKEN = data["NOTION_TOKEN"]
    return NOTION_TOKEN

NOTION_TOKEN = get_notion_token()

# Your My Space page ID
PARENT_PAGE_ID = "3d6e46567a3a8095a301c71623358b21"

# ============================================================
# CLIENT
# ============================================================

notion = Client(auth=NOTION_TOKEN)


# ============================================================
# HELPERS
# ============================================================


def rich_text(value):
    """Create a Notion rich-text property value."""
    return {"rich_text": [{"type": "text", "text": {"content": value}}]}


def title_property(name):
    return {name: {"title": {}}}


def text_property(name):
    return {name: {"rich_text": {}}}


def select_property(name, options):
    return {name: {"select": {"options": [{"name": option} for option in options]}}}


def multi_select_property(name, options):
    return {
        name: {"multi_select": {"options": [{"name": option} for option in options]}}
    }


def date_property(name):
    return {name: {"date": {}}}


def checkbox_property(name):
    return {name: {"checkbox": {}}}


def url_property(name):
    return {name: {"url": {}}}


def number_property(name, format="number"):
    return {name: {"number": {"format": format}}}


def create_page(parent_id, title, icon="📁"):
    """Create a simple child page."""

    print(f"Creating page: {title}")

    response = notion.pages.create(
        parent={"page_id": parent_id},
        icon={"type": "emoji", "emoji": icon},
        properties={"title": {"title": [{"type": "text", "text": {"content": title}}]}},
    )

    return response["id"]


def create_database(parent_id, name, icon, properties):
    """Create a database under a page."""

    print(f"Creating database: {name}")

    response = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_id},
        icon={"type": "emoji", "emoji": icon},
        title=[{"type": "text", "text": {"content": name}}],
        properties=properties,
    )

    return response["id"]


def add_text_to_page(page_id, heading, text):
    """Add introductory content to a page."""

    notion.blocks.children.append(
        block_id=page_id,
        children=[
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": heading}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            },
        ],
    )


# ============================================================
# MAIN SETUP
# ============================================================


def main():

    print()
    print("=" * 60)
    print("       NOTION PERSONAL HUB SETUP")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # Test connection
    # --------------------------------------------------------

    print("Testing Notion connection...")

    try:
        me = notion.users.me()
        print(f"Connected successfully.")
        print(f"Integration: {me.get('name', 'Unknown')}")
    except Exception as e:
        print()
        print("ERROR: Could not connect to Notion.")
        print(e)
        print()
        print("Check:")
        print("1. Your NOTION_TOKEN is correct.")
        print("2. The integration has access to My Space.")
        return

    print()

    # --------------------------------------------------------
    # Create section pages
    # --------------------------------------------------------

    print("Creating Personal Hub sections...")
    print()

    notes_page = create_page(PARENT_PAGE_ID, "Notes", "📝")

    tasks_page = create_page(PARENT_PAGE_ID, "Tasks", "✅")

    trips_page = create_page(PARENT_PAGE_ID, "Trips", "✈️")

    career_page = create_page(PARENT_PAGE_ID, "Career", "💼")

    media_page = create_page(PARENT_PAGE_ID, "Media", "🎬")

    ideas_page = create_page(PARENT_PAGE_ID, "Ideas", "💡")

    journal_page = create_page(PARENT_PAGE_ID, "Journal", "📔")

    # --------------------------------------------------------
    # NOTES DATABASE
    # --------------------------------------------------------

    notes_db = create_database(
        notes_page,
        "Notes",
        "📝",
        {
            **title_property("Note"),
            **select_property(
                "Type",
                [
                    "Personal",
                    "Reference",
                    "Learning",
                    "Work",
                    "Travel",
                    "Idea",
                    "Other",
                ],
            ),
            **multi_select_property(
                "Tags",
                ["Important", "Reference", "Personal", "Work", "Travel", "Learning"],
            ),
            **select_property("Status", ["Active", "Archived"]),
            **date_property("Created"),
        },
    )

    # --------------------------------------------------------
    # TASKS DATABASE
    # --------------------------------------------------------

    tasks_db = create_database(
        tasks_page,
        "Tasks",
        "✅",
        {
            **title_property("Task"),
            **select_property(
                "Status",
                ["Inbox", "Next", "In Progress", "Waiting", "Done", "Cancelled"],
            ),
            **select_property("Priority", ["Low", "Medium", "High", "Urgent"]),
            **date_property("Due Date"),
            **multi_select_property(
                "Category",
                ["Personal", "Work", "Career", "Travel", "Finance", "Health", "Other"],
            ),
            **checkbox_property("Completed"),
            **text_property("Notes"),
        },
    )

    # --------------------------------------------------------
    # TRIPS DATABASE
    # --------------------------------------------------------

    trips_db = create_database(
        trips_page,
        "Trips",
        "✈️",
        {
            **title_property("Trip"),
            **date_property("Start Date"),
            **date_property("End Date"),
            **text_property("Location"),
            **select_property(
                "Status",
                ["Idea", "Planning", "Booked", "Ongoing", "Completed", "Cancelled"],
            ),
            **multi_select_property("People", ["Solo", "Friends", "Family", "Office"]),
            **number_property("Budget", "rupee"),
            **number_property("Actual Spend", "rupee"),
            **url_property("Polarsteps"),
            **text_property("Highlights"),
        },
    )

    # --------------------------------------------------------
    # CAREER DATABASE
    # --------------------------------------------------------

    career_db = create_database(
        career_page,
        "Career",
        "💼",
        {
            **title_property("Item"),
            **select_property(
                "Type",
                [
                    "Learning",
                    "Project",
                    "Job",
                    "Interview",
                    "Certification",
                    "Idea",
                    "Reference",
                ],
            ),
            **select_property(
                "Status", ["Not Started", "In Progress", "Completed", "On Hold"]
            ),
            **multi_select_property(
                "Skills",
                [
                    "Python",
                    "DevOps",
                    "Cloud",
                    "Docker",
                    "Kubernetes",
                    "CI/CD",
                    "Automation",
                    "Development",
                    "AI/ML",
                ],
            ),
            **url_property("Link"),
            **date_property("Date"),
            **text_property("Notes"),
        },
    )

    # --------------------------------------------------------
    # MEDIA DATABASE
    # --------------------------------------------------------

    media_db = create_database(
        media_page,
        "Media",
        "🎬",
        {
            **title_property("Title"),
            **select_property(
                "Type",
                [
                    "Movie",
                    "Series",
                    "Book",
                    "Podcast",
                    "Fanfiction",
                    "YouTube",
                    "Other",
                ],
            ),
            **select_property(
                "Status", ["Want to Watch", "Watching", "Completed", "Dropped"]
            ),
            **number_property("Rating", "number"),
            **url_property("Link"),
            **text_property("Notes"),
        },
    )

    # --------------------------------------------------------
    # IDEAS DATABASE
    # --------------------------------------------------------

    ideas_db = create_database(
        ideas_page,
        "Ideas",
        "💡",
        {
            **title_property("Idea"),
            **select_property(
                "Status",
                ["New", "Thinking", "Researching", "Working On", "Done", "Dropped"],
            ),
            **multi_select_property(
                "Category",
                [
                    "Personal",
                    "Career",
                    "Travel",
                    "Technology",
                    "AI",
                    "Creative",
                    "Random",
                ],
            ),
            **date_property("Created"),
            **text_property("Notes"),
        },
    )

    # --------------------------------------------------------
    # JOURNAL DATABASE
    # --------------------------------------------------------

    journal_db = create_database(
        journal_page,
        "Journal",
        "📔",
        {
            **title_property("Entry"),
            **date_property("Date"),
            **select_property("Mood", ["Great", "Good", "Okay", "Low", "Difficult"]),
            **multi_select_property(
                "Tags", ["Life", "Travel", "Career", "Reflection", "Memory", "Idea"]
            ),
            **text_property("Summary"),
        },
    )

    # --------------------------------------------------------
    # ADD INTRODUCTORY TEXT
    # --------------------------------------------------------

    add_text_to_page(
        notes_page,
        "About Notes",
        "Use this database for information you want to remember rather than tasks you need to complete.",
    )

    add_text_to_page(
        tasks_page,
        "About Tasks",
        "Use this database for things that require an action. Use Due Date for time-sensitive tasks.",
    )

    add_text_to_page(
        trips_page,
        "About Trips",
        "Your permanent travel archive. Add photos, videos, journal entries, expenses and your Polarsteps link inside each trip.",
    )

    add_text_to_page(
        career_page,
        "About Career",
        "Keep learning, projects, job preparation, interviews and technical knowledge here.",
    )

    add_text_to_page(
        media_page,
        "About Media",
        "Track movies, series, books, podcasts and other media.",
    )

    add_text_to_page(
        ideas_page,
        "About Ideas",
        "A place for random thoughts, projects and ideas before deciding what to do with them.",
    )

    add_text_to_page(
        journal_page,
        "About Journal",
        "Your chronological personal journal. Each entry can contain text, images, videos, files and anything else you want.",
    )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("             SETUP COMPLETE 🎉")
    print("=" * 60)
    print()

    print("Created pages:")
    print(f"Notes   : {notes_page}")
    print(f"Tasks   : {tasks_page}")
    print(f"Trips   : {trips_page}")
    print(f"Career  : {career_page}")
    print(f"Media   : {media_page}")
    print(f"Ideas   : {ideas_page}")
    print(f"Journal : {journal_page}")

    print()
    print("Created databases:")
    print(f"Notes   : {notes_db}")
    print(f"Tasks   : {tasks_db}")
    print(f"Trips   : {trips_db}")
    print(f"Career  : {career_db}")
    print(f"Media   : {media_db}")
    print(f"Ideas   : {ideas_db}")
    print(f"Journal : {journal_db}")

    print()
    print("Open Notion and check your My Space page.")
    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    try:
        main()

    except APIResponseError as error:
        print()
        print("=" * 60)
        print("NOTION API ERROR")
        print("=" * 60)
        print()
        print(error)
        print()
        print("Common causes:")
        print("- Integration does not have access to My Space.")
        print("- Token is incorrect.")
        print("- Parent page ID is incorrect.")
        print("- Notion API permission/feature limitation.")
        print()

    except Exception as error:
        print()
        print("=" * 60)
        print("UNEXPECTED ERROR")
        print("=" * 60)
        print()
        print(error)
        print()
