import frappe, requests

def notify_raven(decision_doc, channel_webhook=None):
    if not channel_webhook:
        channel_webhook = frappe.db.get_single_value("System Settings", "raven_webhook_url") or None
    if not channel_webhook:
        return
    msg = f"📌 *Decision* `{decision_doc.name}`\n*Title:* {decision_doc.title}\n*Project:* {decision_doc.project or '-'}\n*Status:* {decision_doc.status}\n*Chosen:* {decision_doc.chosen_option or '-'}"
    try:
        requests.post(channel_webhook, json={"text": msg}, timeout=4)
    except Exception:
        frappe.log_error("Raven notify failed", "Decision Ledger")
