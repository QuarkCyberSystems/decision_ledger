import frappe
from frappe.utils import nowdate, cstr, flt
from .todo_digest import format_todo_markdown, format_todo_summary_markdown
from .todo_bot_tasks import send_full_digest_to_user, send_summary_to_user

@frappe.whitelist()
def create_task(subject, project=None, team_member=None, budgeted_hours=None, assign_to=None,
                priority="Medium", due_date=None, description=None):
    """
    Create a Task (and optionally a ToDo assignment) from Raven.

    Args:
        subject (str): Task subject (required)
        project (str): Project name (optional)
        team_member (str): User (email/name) for a single child row (optional)
        budgeted_hours (float): Hours for that single row (optional)
        assign_to (str): User (email/name) to assign via ToDo (optional)
        priority (str): Low | Medium | High (default Medium)
        due_date (str): YYYY-MM-DD → sets exp_end_date (optional)
        description (str): Task description (optional)

    Returns:
        dict: { ok: True, task: "<Task Name>", todo: "<ToDo Name>" (if created) }
    """
    subject = (subject or "").strip()
    if not subject:
        frappe.throw("subject is required")

    task = frappe.new_doc("Task")
    task.subject = subject
    task.project = project
    task.priority = (priority or "Medium").title()
    task.exp_start_date = nowdate()
    if due_date:
        task.exp_end_date = due_date
    if description:
        task.description = description

    # Child table: custom_budgeted_time (team_member, budgeted_hours)
    if team_member and budgeted_hours:
        task.append("custom_budgeted_time", {
            "team_member": cstr(team_member).strip(),
            "budgeted_hours": flt(budgeted_hours)
        })

    task.insert()  # uses current session's permissions

    result = {"ok": True, "task": task.name}

    # Create a ToDo (assignment) if assign_to provided
    if assign_to:
        todo = frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": cstr(assign_to).strip(),
            "reference_type": "Task",
            "reference_name": task.name,
            "description": task.subject,
        }).insert()

        # Optionally share the Task so assignee has write access in Desk
        try:
            frappe.share.add("Task", task.name, cstr(assign_to).strip(), read=1, write=1, share=0)
        except Exception:
            frappe.log_error(f"Share failed for Task {task.name} → {assign_to}", "create_task")

        result["todo"] = todo.name

    return result





@frappe.whitelist()  # called inside a logged-in Raven session
def todo_digest_for(user: str = None):
    """Return grouped ToDo digest markdown for a user (defaults to current)."""
    u = user or frappe.session.user
    # Hard guard: only the user themselves or System Manager can request others' digests
    if user and user != frappe.session.user and not frappe.has_permission("User", "read"):
        frappe.throw("Not permitted", frappe.PermissionError)
    return {"ok": True, "user": u, "markdown": format_todo_markdown(u)}




@frappe.whitelist()
def mytodos_full():
    send_full_digest_to_user(frappe.session.user)
    return {"ok": True}

@frappe.whitelist()
def mytodos_summary(preview_per_section: int = 2):
    send_summary_to_user(frappe.session.user, int(preview_per_section))
    return {"ok": True}


def _bot():
    return frappe.get_doc("Raven Bot", "todo-bot")

@frappe.whitelist()
def agent_todo_digest(args=None, user_email: str | None = None, mode: str = "summary",
                      preview_per_section: int = 2, send_dm: int = 1):
    """
    Raven Agent Function: return and/or DM the user's ToDo digest.

    Supports two call styles:
      1) agent passes a single dict: agent_todo_digest(args)
      2) normal RPC passes kwargs: agent_todo_digest(user_email=..., mode=..., ...)

    Args in dict form:
      { "user_email": "...", "mode": "summary|full", "preview_per_section": 2, "send_dm": 1 }
    """
    # --- Unpack if called with a single dict positional argument ---
    if isinstance(args, dict):
        user_email = args.get("user_email", user_email)
        mode = args.get("mode", mode) or "summary"
        preview_per_section = int(args.get("preview_per_section", preview_per_section or 2) or 2)
        send_dm = int(args.get("send_dm", send_dm or 1) or 1)

    # If agent sent JSON string in args (rare), try to parse
    if isinstance(args, str) and args.strip().startswith("{"):
        try:
            d = frappe.parse_json(args)
            user_email = d.get("user_email", user_email)
            mode = d.get("mode", mode) or "summary"
            preview_per_section = int(d.get("preview_per_section", preview_per_section or 2) or 2)
            send_dm = int(d.get("send_dm", send_dm or 1) or 1)
        except Exception:
            pass  # fall back to defaults

    user = user_email or frappe.session.user
    if mode == "full":
        md = format_todo_markdown(user)
    else:
        md = format_todo_summary_markdown(user, int(preview_per_section))

    if int(send_dm):
        _bot().send_direct_message(user_id=user, text=md, markdown=True)

    return {"ok": True, "user": user, "mode": mode, "markdown": md}