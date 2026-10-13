import frappe
from frappe import _

TICKET_FIELDS = ["name", "event", "registration_id", "attendee_name", "ticket_type", "organisation", "country"]


def get_my_ticket() -> frappe._dict:
	"""The signed-in participant's newest active Event Ticket."""
	tickets = frappe.get_all(
		"Event Ticket",
		filters={"user": frappe.session.user, "docstatus": 1},
		fields=TICKET_FIELDS,
		order_by="creation desc",
		limit=1,
	)
	if not tickets:
		frappe.throw(_("No active registration found"), frappe.PermissionError)
	return tickets[0]


def get_ticket_by_registration_id(registration_id: str, event: str) -> frappe._dict:
	tickets = frappe.get_all(
		"Event Ticket",
		filters={"registration_id": registration_id, "event": event, "docstatus": 1},
		fields=TICKET_FIELDS + ["show_in_directory"],
		limit=1,
	)
	if not tickets:
		frappe.throw(_("Participant not found"))
	return tickets[0]
