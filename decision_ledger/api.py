import frappe
from frappe.utils import nowdate, cstr, flt, cint
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


@frappe.whitelist()
def get_projects_overview(search: str | None = None, limit: int = 50, status: str | None = None):
    """
    Return a list of projects with key rollups:
    - Owner/PM
    - Task counts (total, open, closed)
    - Hours (Timesheet Detail for submitted timesheets)
    - Cost so far (costing_amount), Billing so far (billing_amount)
    - Budget (from Project.estimated_costing or custom budget_cost)
    - Current assignees (From ToDo on Tasks, open only)
    """
    limit = cint(limit or 50)

    # Detect whether Project has 'project_manager' column (older builds may not)
    has_pm_col = frappe.db.has_column("Project", "project_manager")
    pm_select = "p.project_manager" if has_pm_col else "NULL AS project_manager"

    # 1) Base project list
    where = ["1=1"]
    params = {}
    if status:
        where.append("p.status=%(status)s")
        params["status"] = status
    if search:
        where.append("(p.name LIKE %(q)s OR p.project_name LIKE %(q)s)")
        params["q"] = f"%{search}%"

    projects = frappe.db.sql(f"""
        SELECT
            p.name, p.project_name, p.company, p.status,
            p.expected_start_date, p.expected_end_date,
            {pm_select},
            COALESCE(p.estimated_costing, p.total_costing_amount, 0) AS estimated_costing
        FROM `tabProject` p
        WHERE {" AND ".join(where)}
        ORDER BY p.modified DESC
        LIMIT {limit}
    """, params, as_dict=True)

    if not projects:
        return {"ok": True, "data": []}

    proj_names = [r["name"] for r in projects]
    in_clause = ", ".join(["%s"] * len(proj_names))

    # 3) Task counts per project
    task_stats = { }
    for r in frappe.db.sql(f"""
        SELECT
            t.project,
            COUNT(*) AS total,
            SUM(CASE WHEN t.status IN ('Open','Working') THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE WHEN t.status IN ('Completed','Cancelled') THEN 1 ELSE 0 END) AS closed_count
        FROM `tabTask` t
        WHERE t.project IN ({in_clause})
        GROUP BY t.project
    """, proj_names, as_dict=True):
        task_stats[r["project"]] = r

    # 4) Hours + Cost/Billing from Timesheets (submitted)
    ts_map = {}
    for r in frappe.db.sql(f"""
        SELECT d.project,
               SUM(d.hours) AS hours,
               SUM(d.costing_amount) AS cost,
               SUM(d.billing_amount) AS billed
        FROM `tabTimesheet Detail` d
        JOIN `tabTimesheet` ts ON ts.name=d.parent AND ts.docstatus=1
        WHERE d.project IN ({in_clause})
        GROUP BY d.project
    """, proj_names, as_dict=True):
        ts_map[r["project"]] = r

    # 5) Assignees (distinct open ToDo owners on Tasks of this project)
    assignees_map = {}
    for r in frappe.db.sql(f"""
        SELECT DISTINCT t.project, td.allocated_to AS user
        FROM `tabToDo` td
        JOIN `tabTask` t ON t.name = td.reference_name
        WHERE td.reference_type='Task' AND td.status!='Closed'
          AND t.project IN ({in_clause}) AND IFNULL(td.allocated_to,'')!=''
    """, proj_names, as_dict=True):
        assignees_map.setdefault(r["project"], []).append(r["user"])

    # Also consider Task owners of active tasks (Open/Working) as assignees fallback
    for r in frappe.db.sql(f"""
        SELECT DISTINCT t.project, t.owner AS user
        FROM `tabTask` t
        WHERE t.project IN ({in_clause})
          AND t.status IN ('Open','Working')
          AND IFNULL(t.owner,'') != ''
    """, proj_names, as_dict=True):
        assignees_map.setdefault(r["project"], []).append(r["user"])

    # 5) Members (Project Users without role filter)
    members_map = {}
    for r in frappe.db.sql(f"""
        SELECT pu.parent AS project, pu.user
        FROM `tabProject User` pu
        WHERE pu.parent IN ({in_clause})
    """, proj_names, as_dict=True):
        members_map.setdefault(r["project"], []).append(r["user"])

    # Enabled users (system users) for filtering
    enabled_users = set(frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"}, pluck="name"))

    # Build response
    out = []
    for p in projects:
        nm = p["name"]
        ts = ts_map.get(nm, {}) or {}
        st = task_stats.get(nm, {}) or {}
        out.append({
            "name": nm,
            "project_name": p["project_name"],
            "company": p["company"],
            "status": p["status"],
            "start": p["expected_start_date"],
            "end": p["expected_end_date"],
            "manager": p.get("project_manager") or None,
            "tasks": {
                "total": cint(st.get("total") or 0),
                "open": cint(st.get("open_count") or 0),
                "closed": cint(st.get("closed_count") or 0),
            },
            "hours": flt(ts.get("hours") or 0.0),
            "cost": {
                "spent": flt(ts.get("cost") or 0.0),
                "billed": flt(ts.get("billed") or 0.0),
                "budget": flt(p.get("estimated_costing") or 0.0)  # adjust if you use a custom budget field
            },
            # Build cleaned assignee list: prefer ToDo/owner-derived; fallback to project members
            "assignees": (lambda _raw, _fallback: sorted(
                {u for u in (_raw if _raw else _fallback)
                 if u and u.lower() not in ("administrator", "guest") and u in enabled_users}
            ))(assignees_map.get(nm, []) or [], members_map.get(nm, []) or []),
            "members": sorted(set(members_map.get(nm, []))),
        })
    return {"ok": True, "data": out}

@frappe.whitelist()
def get_project_detail(project: str):
    """Detailed drilldown for one project: top open tasks, recent timesheets, members."""
    # light sample; expand as needed
    detail = {"project": project}

    pr = frappe.db.get_value("Project", project,
        ["name","project_name","company","status","expected_start_date","expected_end_date","percent_complete"],
        as_dict=True)
    detail["info"] = pr

    tasks = frappe.get_all("Task",
        filters={"project": project},
        fields=["name","subject","status","priority","exp_end_date","modified"],
        order_by="CASE WHEN exp_end_date IS NULL THEN 1 ELSE 0 END ASC, exp_end_date ASC, modified DESC",
        limit=50)
    detail["tasks"] = tasks

    tlogs = frappe.db.sql("""
        SELECT ts.name as timesheet, d.hours, d.billing_amount, d.costing_amount, d.activity_type, d.task, ts.start_date, ts.end_date
        FROM `tabTimesheet Detail` d
        JOIN `tabTimesheet` ts ON ts.name=d.parent AND ts.docstatus=1
        WHERE d.project=%s
        ORDER BY ts.modified DESC
        LIMIT 50
    """, project, as_dict=True)
    detail["timesheets"] = tlogs

    members = frappe.get_all("Project User", filters={"parent": project}, fields=["user"])
    detail["members"] = members

    return {"ok": True, "data": detail}