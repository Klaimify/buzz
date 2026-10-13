import frappe
from frappe import _
from frappe.utils import getdate

from buzz.participants import meetings
from buzz.participants.session import get_my_ticket, get_ticket_by_registration_id


@frappe.whitelist()
def list_slots() -> list[dict]:
	"""Open slots for the participant's event, with how many tables are still free."""
	ticket = get_my_ticket()
	slots = frappe.get_all(
		"Meeting Slot",
		filters={"event": ticket.event},
		fields=["name", "date", "start_time", "end_time", "tables"],
		order_by="date asc, start_time asc",
	)
	active_meetings = frappe.get_all(
		"Meeting Request",
		filters={"event": ticket.event, "status": ("in", meetings.ACTIVE_STATUSES)},
		fields=["slot", "requester", "invitee"],
	)
	for slot in slots:
		slot_meetings = [meeting for meeting in active_meetings if meeting.slot == slot.name]
		slot["free_tables"] = slot.tables - len(slot_meetings)
		slot["i_am_busy"] = any(ticket.name in (meeting.requester, meeting.invitee) for meeting in slot_meetings)
		slot["date"] = str(getdate(slot.date))
		slot["start_time"] = str(slot.start_time)
		slot["end_time"] = str(slot.end_time)
	return slots


@frappe.whitelist()
def request_meeting(registration_id: str, slot: str, message: str | None = None) -> dict:
	requester = get_my_ticket()
	invitee = get_ticket_by_registration_id(registration_id, requester.event)
	name = meetings.request_meeting(requester, invitee, slot, message)
	return {"meeting": name}


@frappe.whitelist()
def respond(meeting: str, action: str) -> dict:
	ticket = get_my_ticket()
	return {"status": meetings.respond_to_meeting(meeting, ticket.name, action)}


@frappe.whitelist()
def my_meetings() -> list[dict]:
	ticket = get_my_ticket()
	rows = frappe.get_all(
		"Meeting Request",
		filters=[["Meeting Request", "requester", "=", ticket.name]],
		or_filters=[["Meeting Request", "invitee", "=", ticket.name]],
		fields=["name", "requester", "invitee", "slot", "table_no", "status", "message"],
		order_by="creation desc",
	)
	slot_names = list({row.slot for row in rows})
	slots = {
		slot.name: slot
		for slot in frappe.get_all(
			"Meeting Slot", filters={"name": ("in", slot_names)}, fields=["name", "date", "start_time", "end_time"]
		)
	}
	ticket_names = list({row.requester for row in rows} | {row.invitee for row in rows})
	people = {
		person.name: person
		for person in frappe.get_all(
			"Event Ticket",
			filters={"name": ("in", ticket_names)},
			fields=["name", "attendee_name", "organisation", "registration_id"],
		)
	}
	result = []
	for row in rows:
		other = people.get(row.invitee if row.requester == ticket.name else row.requester)
		slot = slots.get(row.slot)
		result.append(
			{
				"name": row.name,
				"status": row.status,
				"table_no": row.table_no,
				"message": row.message,
				"direction": "outgoing" if row.requester == ticket.name else "incoming",
				"with": {
					"name": other.attendee_name,
					"organisation": other.organisation,
					"registration_id": other.registration_id,
				}
				if other
				else None,
				"date": str(getdate(slot.date)) if slot else None,
				"start_time": str(slot.start_time) if slot else None,
				"end_time": str(slot.end_time) if slot else None,
			}
		)
	return result
