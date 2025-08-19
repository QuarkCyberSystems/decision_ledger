import frappe
from .todo_digest import format_todo_markdown, format_todo_summary_markdown

def _bot():
    return frappe.get_doc("Raven Bot", "todo-bot")

def send_full_digest_to_user(user_id: str):
    _bot().send_direct_message(user_id=user_id, text=format_todo_markdown(user_id), markdown=True)

def send_summary_to_user(user_id: str, preview_per_section: int = 2):
    _bot().send_direct_message(user_id=user_id, text=format_todo_summary_markdown(user_id, preview_per_section), markdown=True)

def users_with_open_todos():
    return frappe.get_all(
        "ToDo",
        filters={"status": ["!=", "Closed"]},
        distinct=True,
        pluck="allocated_to"
    )
