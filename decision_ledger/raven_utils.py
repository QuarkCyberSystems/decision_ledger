import frappe


def raven_available() -> bool:
    """True only when the Raven app is installed and its Bot DocType exists.

    Lets the ToDo-digest delivery paths degrade gracefully when Raven is not
    installed on the site instead of throwing on `frappe.get_doc("Raven Bot", ...)`.
    """
    if "raven" not in frappe.get_installed_apps():
        return False
    return bool(frappe.db.exists("DocType", "Raven Bot"))


def log_raven_skip(message: str):
    """Write a visible breadcrumb to logs/decision_ledger.log when a
    Raven-dependent action is intentionally skipped.

    Frappe's module loggers default to ERROR level (when `conf.logging` is unset),
    so set INFO explicitly here — otherwise the breadcrumb is filtered out before it
    reaches the file handlers. Avoids `frappe.log_error`, which would create an Error
    Log entry and read like a failure rather than an intentional no-op.
    """
    logger = frappe.logger("decision_ledger")
    logger.setLevel("INFO")
    logger.info(message)
