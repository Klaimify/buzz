# Copyright (c) 2025, BWH Studios and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class ScanQR(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF


	# end: auto-generated types
	pass

@frappe.whitelist()
def verify_qr(qr):
    print("=== QR RECEIVED ===", qr)
    
    reg = frappe.db.get_value(
        "Event Ticket",
        {"name": qr},
        ["name", "attendee_name", "event"],
        as_dict=True
    )
    
    print("=== REGISTRATION FOUND ===", reg)

    if not reg:
        return None

    # Check if already checked in
    checked_in = frappe.db.exists(
        "Event Check In",
        {"ticket": qr, "docstatus": 1}
    )

    # Add checked_in status to the response
    reg["checked_in"] = bool(checked_in)

    return reg



@frappe.whitelist()
def mark_checked_in(name):
    # Mark registration as checked in
    # frappe.db.set_value("Event Registration", name, "checked_in", True)
    existing = frappe.db.exists(
        "Event Check In",
        {"ticket": name, "docstatus": 1}  # docstatus=1 means submitted
    )
    if existing:
        # Already checked in
        return {"status": "already_checked_in"}
    # Create a check-in log entry
    doc = frappe.new_doc("Event Check In")
    doc.attendee = name
    doc.ticket = name
    doc.event = frappe.db.get_value("Event Ticket", name, "event")
    doc.checkin_time = now_datetime()
    doc.insert(ignore_permissions=True)
    doc.submit()

    return True
