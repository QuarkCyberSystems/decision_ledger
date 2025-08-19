import frappe
from frappe.utils import nowdate, cstr, flt

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
