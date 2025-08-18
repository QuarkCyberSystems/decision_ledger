import frappe

def after_install():
    add_decision_link_to_project()

def add_decision_link_to_project():
    """Add 'Decision' to Project > Connections, linked via Decision.project."""
    if not frappe.db.exists("DocType", "Project"):
        return

    # already present?
    exists = frappe.db.exists(
        "DocType Link",
        {
            "parent": "Project",
            "parenttype": "DocType",
            "parentfield": "links",
            "link_doctype": "Decision",
            "link_fieldname": "project",
        },
    )
    if exists:
        return

    row = frappe.get_doc({
        "doctype": "DocType Link",
        "parent": "Project",
        "parenttype": "DocType",
        "parentfield": "links",
        "link_doctype": "Decision",
        "link_fieldname": "project",
        # optional: group label seen in Connections drawer
        "group": "Decisions"
    })
    row.insert(ignore_permissions=True)
    frappe.db.commit()
