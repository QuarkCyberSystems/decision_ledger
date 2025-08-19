
import frappe
from .todo_digest import format_todo_markdown

def _get_users_with_open_todos():
    rows = frappe.db.sql("""
        select distinct allocated_to
        from `tabToDo`
        where status != 'Closed' and ifnull(allocated_to, '') != ''
    """, as_dict=True)
    # Filter out disabled or non-system users
    users = [r.allocated_to for r in rows if frappe.db.get_value("User", r.allocated_to, "enabled")]
    return users

def _get_or_create_dm_channel(user_email: str):
    """Best-effort creation of a DM channel with your bot user.
       Adjust to your Raven setup (bot user name/email).
    """
    bot_user = frappe.db.get_single_value("Raven Settings", "bot_user") or "Administrator"
    # Try to find existing direct channel
    existing = frappe.get_all("Raven Channel", filters={
        "type": "Direct"
    }, or_filters=[
        ["members", "like", f"%{user_email}%"],
        ["members", "like", f"%{bot_user}%"]
    ], fields=["name"], limit=1)
    if existing:
        return existing[0]["name"]

    # Fallback create – your Raven version may differ; adapt fields accordingly
    ch = frappe.get_doc({
        "doctype": "Raven Channel",
        "channel_name": f"dm-{user_email}",
        "type": "Direct",
        "members": [{"user": bot_user}, {"user": user_email}]
    }).insert(ignore_permissions=True)
    return ch.name

def _send_dm(user_email: str, markdown: str):
    channel = _get_or_create_dm_channel(user_email)
    # Minimal message insert – adjust field names to your Raven build if needed
    frappe.get_doc({
        "doctype": "Raven Message",
        "channel": channel,
        "message_type": "Text",
        "message": markdown
    }).insert(ignore_permissions=True)

def send_daily_todo_digests():
    """Cron: run once a day (05:00 UTC) and DM all users their ToDo digest."""
    users = _get_users_with_open_todos()
    for u in users:
        try:
            md = format_todo_markdown(u)
            if md and "None" not in md:  # optional: skip totally empty digests
                _send_dm(u, md)
        except Exception as e:
            frappe.log_error(f"ToDo digest failed for {u}: {e}", "todo_notifier")
