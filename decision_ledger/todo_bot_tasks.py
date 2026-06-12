import frappe
from .todo_digest import format_todo_markdown, format_todo_summary_markdown
from .raven_utils import raven_available

def _bot():
    return frappe.get_doc("Raven Bot", "todo-bot")

def send_full_digest_to_user(user_id: str) -> bool:
    """DM the user their full ToDo digest. Returns False (no-op) if Raven is absent."""
    if not raven_available():
        return False
    _bot().send_direct_message(user_id=user_id, text=format_todo_markdown(user_id), markdown=True)
    return True

def send_summary_to_user(user_id: str, preview_per_section: int = 2) -> bool:
    """DM the user their ToDo summary. Returns False (no-op) if Raven is absent."""
    if not raven_available():
        return False
    _bot().send_direct_message(user_id=user_id, text=format_todo_summary_markdown(user_id, preview_per_section), markdown=True)
    return True

def users_with_open_todos():
    return frappe.get_all(
        "ToDo",
        filters={"status": ["!=", "Closed"]},
        distinct=True,
        pluck="allocated_to"
    )
