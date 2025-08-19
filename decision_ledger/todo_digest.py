import frappe
from frappe.utils import getdate, nowdate, add_days, format_datetime

def _range_week(date):
    d = getdate(date)
    start = add_days(d, -d.weekday())      # Monday
    end = add_days(start, 6)               # Sunday
    return start, end

def _range_month(date):
    d = getdate(date)
    start = d.replace(day=1)
    if d.month == 12:
        next_first = d.replace(year=d.year+1, month=1, day=1)
    else:
        next_first = d.replace(month=d.month+1, day=1)
    end = add_days(next_first, -1)
    return start, end

def fetch_user_todos(user: str):
    """Active ToDos for a user (status != Closed). Order: dated first, undated last."""
    return frappe.get_all(
        "ToDo",
        filters={
            "allocated_to": user,
            "status": ["!=", "Closed"],
        },
        fields=[
            "name", "description", "date",
            "reference_type", "reference_name",
            "priority", "status", "modified"
        ],
        # Portable "NULLS LAST" using a CASE expression
        order_by=(
            "CASE WHEN `tabToDo`.`date` IS NULL THEN 1 ELSE 0 END ASC, "
            "`tabToDo`.`date` ASC, "
            "`tabToDo`.`modified` DESC"
        ),
    )

def group_todos(user: str):
    today = getdate(nowdate())
    wk_start, wk_end = _range_week(today)
    mo_start, mo_end = _range_month(today)

    today_list, week_list, month_list, later_list, nodue_list = [], [], [], [], []

    for t in fetch_user_todos(user):
        if not t.get("date"):
            nodue_list.append(t); continue
        due = getdate(t["date"])
        if due == today:
            today_list.append(t)
        elif wk_start <= due <= wk_end:
            week_list.append(t)
        elif mo_start <= due <= mo_end:
            month_list.append(t)
        elif due > mo_end:
            later_list.append(t)

    return {
        "today": today_list,
        "week": week_list,
        "month": month_list,
        "later": later_list,
        "nodue": nodue_list
    }

# --- Full (detailed) markdown you already use ---
def format_todo_markdown(user: str):
    g = group_todos(user)
    def _fmt(items):
        if not items: return "_None_"
        rows = []
        for t in items:
            ref = ""
            if t.get("reference_type") and t.get("reference_name"):
                ref = f"  ·  {t['reference_type']}: `{t['reference_name']}`"
            due = f" (Due: {t['date']})" if t.get("date") else ""
            pr = f"[{t.get('priority','')}] " if t.get("priority") else ""
            rows.append(f"- {pr}{t.get('description') or t['name']}{due}{ref}")
        return "\n".join(rows)

    hdr = f"*Your ToDos – {format_datetime(nowdate())}*"
    parts = [
        hdr,
        "\n*Due Today*",
        _fmt(g["today"]),
        "\n*Due This Week*",
        _fmt(g["week"]),
        "\n*Due This Month*",
        _fmt(g["month"]),
    ]
    if g["later"]: parts += ["\n*Later*", _fmt(g["later"])]
    if g["nodue"]: parts += ["\n*No Due Date*", _fmt(g["nodue"])]
    return "\n".join(parts).strip()

# --- NEW: Summary mode (counts, optional previews) ---
def format_todo_summary_markdown(user: str, preview_per_section: int = 2):
    g = group_todos(user)

    def _count(items): return len(items or [])
    def _preview(items, n):
        if not items or n <= 0: return ""
        rows = []
        for t in items[:n]:
            due = f" · {t['date']}" if t.get("date") else ""
            rows.append(f"  - {t.get('description') or t['name']}{due}")
        return "\n".join(rows)

    # counts
    c_today, c_week, c_month = _count(g["today"]), _count(g["week"]), _count(g["month"])
    c_later, c_nodue = _count(g["later"]), _count(g["nodue"])

    total = c_today + c_week + c_month + c_later + c_nodue
    if total == 0:
        return "*✅ You’re all clear — no open ToDos!*"

    hdr = f"*Your ToDo Summary – {format_datetime(nowdate())}*"
    lines = [
        hdr,
        f"- **Due Today:** {c_today}",
        f"- **Due This Week:** {c_week}",
        f"- **Due This Month:** {c_month}",
    ]
    if c_later: lines.append(f"- **Later:** {c_later}")
    if c_nodue: lines.append(f"- **No Due Date:** {c_nodue}")

    # Optional quick preview (top N per bucket)
    if preview_per_section > 0:
        def sec(title, items): 
            return f"\n*{title}*\n{_preview(items, preview_per_section)}" if items else ""
        lines += [
            sec("Today", g["today"]),
            sec("This Week", g["week"]),
            sec("This Month", g["month"]),
        ]

    lines.append("\n_Tip: Use `/mytodos` for full list._")
    return "\n".join([l for l in lines if l]).strip()
