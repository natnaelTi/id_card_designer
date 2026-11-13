import frappe
from frappe.utils import add_days, now_datetime


def prune_audit():
    """Only generated-print audit metadata; never designs, Users, profiles or Files."""
    days = int(frappe.get_single("ID Card Settings").audit_retention_days or 90)
    frappe.db.delete("ID Card Print Log", {"creation": ("<", add_days(now_datetime(), -days))})
