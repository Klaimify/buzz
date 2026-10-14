import frappe
from frappe import _
from frappe.utils import getdate, today

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
		"category": frappe.db.get_value("Event Ticket Type", ticket.ticket_type, "title"),
	}


@frappe.whitelist()
def scan_checkin(code: str, scanned_at: str | None = None, gate: str | None = None) -> dict:
	"""
	Staff scan or manual lookup. Idempotent per participant and day: scanning again reports
	"already checked in" instead of failing, so offline queues can be replayed safely.
	`gate` records the entrance used; the first scan of the day decides the gate.
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
		"category": frappe.db.get_value("Event Ticket Type", ticket.ticket_type, "title"),
		"organisation": ticket.organisation,
	}

	# scanned_at lets an offline queue replay a scan on the day it actually happened.
	checkin_date = str(getdate(scanned_at)) if scanned_at else today()
	gate = (gate or "").strip()[:50] or None
	existing = frappe.db.get_value(
		"Event Check In", {"ticket": ticket_name, "date": checkin_date, "docstatus": 1}, ["creation", "gate"], as_dict=True
	)
	if existing:
		return {**result, "status": "already_checked_in", "checked_in_at": existing.creation, "gate": existing.gate}

	checkin = frappe.new_doc("Event Check In")
	checkin.ticket = ticket_name
	checkin.date = checkin_date
	checkin.gate = gate
	# Staff already passed the Frontdesk Manager role check above.
	checkin.insert(ignore_permissions=True)
	checkin.submit()
	return {**result, "status": "checked_in", "checked_in_at": checkin.creation, "gate": gate}


@frappe.whitelist()
def get_gate_stats(date: str | None = None) -> list[dict]:
	"""Check-ins per gate for a day (default today), for the staff scanner screen."""
	frappe.only_for("Frontdesk Manager", True)
	rows = frappe.get_all(
		"Event Check In",
		filters={"date": str(getdate(date)) if date else today(), "docstatus": 1},
		fields=["gate", "count(name) as total"],
		group_by="gate",
	)
	rows.sort(key=lambda row: row.total, reverse=True)
	return [{"gate": row.gate or _("No gate"), "total": row.total} for row in rows]
