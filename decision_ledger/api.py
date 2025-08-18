
import frappe

@frappe.whitelist()
def quick_create(project, title, decision_area=None, description=None, proposed_by=None, decision_impact_type=None, decision_status=None, reference=None):
    d = frappe.new_doc("Decision Ledger")
    d.project = project
    d.decision_area = decision_area
    d.impact_type = decision_impact_type
    d.decision_status = decision_status
    d.description = description
    d.reference = reference
    d.proposed_by = proposed_by or frappe.session.user
    d.insert(ignore_permissions=True)
    return d.name