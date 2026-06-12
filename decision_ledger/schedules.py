import frappe
from .todo_bot_tasks import users_with_open_todos, send_summary_to_user, send_full_digest_to_user
from .raven_utils import raven_available, log_raven_skip

def send_daily_summaries():
    if not raven_available():
        log_raven_skip("Skipping daily ToDo summaries: Raven is not installed")
        return
    for user in users_with_open_todos():
        if not user: continue
        try:
            send_summary_to_user(user, preview_per_section=2)  # short & sweet
        except Exception as e:
            frappe.log_error(f"Daily summary failed for {user}: {e}", "todo-bot")

def send_weekly_full():
    if not raven_available():
        log_raven_skip("Skipping weekly ToDo digest: Raven is not installed")
        return
    for user in users_with_open_todos():
        if not user: continue
        try:
            send_full_digest_to_user(user)
        except Exception as e:
            frappe.log_error(f"Weekly full digest failed for {user}: {e}", "todo-bot")
