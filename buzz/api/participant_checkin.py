import frappe
from frappe import _
from frappe.utils import today

from buzz.participants.qr import build_token, resolve_ticket


@frappe.whitelist()
def get_my_badge() -> dict:
	"""Signed QR token for the signed-in participant's own ticket."""
	tickets = frappe.get_all(
		"Event Ticket",
		filters={"user": frappe.session.user, "docstatus": 1},
		fields=["name", "qr_version", "registration_id", "attendee_name", "ticket_type"],
		order_by="creation desc",
		limit=1,
	)
	if not tickets:
		frappe.throw(_("No active registration found"), frappe.PermissionError)
	ticket = tickets[0]
	return {
		"token": build_token(ticket.name, ticket.qr_version or 1),
		"registration_id": ticket.registration_id,
		"attendee_name": ticket.attendee_name,
		"category": ticket.ticket_type,
	}


@frappe.whitelist()
def scan_checkin(code: str) -> dict:
	"""
	Staff scan or manual lookup. Idempotent per participant and day: scanning again reports
	"already checked in" instead of failing, so offline queues can be replayed safely.
	"""
	frappe.only_for("Frontdesk Manager", True)
	ticket_name = resolve_ticket(code)
	ticket = frappe.db.get_value(
		"Event Ticket",
		ticket_name,
		["registration_id", "attendee_name", "ticket_type", "event", "organisation"],
		as_dict=True,
	)
	result = {
		"registration_id": ticket.registration_id,
		"attendee_name": ticket.attendee_name,
		"category": ticket.ticket_type,
		"organisation": ticket.organisation,
	}

	checkin_date = today()
	existing = frappe.db.get_value("Event Check In", {"ticket": ticket_name, "date": checkin_date}, "creation")
	if existing:
		return {**result, "status": "already_checked_in", "checked_in_at": existing}

	checkin = frappe.new_doc("Event Check In")
	checkin.ticket = ticket_name
	checkin.date = checkin_date
	# Staff already passed the Frontdesk Manager role check above.
	checkin.insert(ignore_permissions=True)
	checkin.submit()
	return {**result, "status": "checked_in", "checked_in_at": checkin.creation}
