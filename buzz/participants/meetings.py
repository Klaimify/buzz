import frappe
from frappe import _

from buzz.participants.push import enqueue_notification

ACTIVE_STATUSES = ["Requested", "Accepted"]


def get_slot_load(slot: str) -> tuple[set[int], set[str]]:
	"""Tables in use and participants busy in a slot (active meetings only)."""
	meetings = frappe.get_all(
		"Meeting Request",
		filters={"slot": slot, "status": ("in", ACTIVE_STATUSES)},
		fields=["table_no", "requester", "invitee"],
	)
	tables = {meeting.table_no for meeting in meetings if meeting.table_no}
	busy = {meeting.requester for meeting in meetings} | {meeting.invitee for meeting in meetings}
	return tables, busy


def request_meeting(requester: frappe._dict, invitee: frappe._dict, slot: str, message: str | None) -> str:
	if requester.name == invitee.name:
		frappe.throw(_("You cannot book a meeting with yourself"))
	if requester.event != invitee.event:
		frappe.throw(_("Participants must be registered for the same event"))

	# Locking the slot row serialises concurrent bookings for the same slot.
	locked_slot = frappe.db.get_value("Meeting Slot", slot, ["name", "event", "tables"], as_dict=True, for_update=True)
	if not locked_slot or locked_slot.event != requester.event:
		frappe.throw(_("Slot not found"))

	tables_in_use, busy_participants = get_slot_load(slot)
	if requester.name in busy_participants or invitee.name in busy_participants:
		frappe.throw(_("One of the participants already has a meeting in this slot"))

	free_tables = [number for number in range(1, locked_slot.tables + 1) if number not in tables_in_use]
	if not free_tables:
		frappe.throw(_("No tables are free in this slot"))

	meeting = frappe.new_doc("Meeting Request")
	meeting.update(
		{
			"event": requester.event,
			"requester": requester.name,
			"invitee": invitee.name,
			"slot": slot,
			"table_no": free_tables[0],
			"message": message,
		}
	)
	# Participants are Website Users with no desk permissions; access is checked by the caller.
	meeting.insert(ignore_permissions=True)
	enqueue_notification(
		[invitee.name],
		_("New meeting request"),
		_("{0} would like to meet you").format(requester.attendee_name),
		{"type": "meeting", "name": meeting.name},
	)
	return meeting.name


def respond_to_meeting(meeting_name: str, ticket: str, action: str) -> str:
	meeting = frappe.get_doc("Meeting Request", meeting_name)
	if action in ("accept", "decline"):
		if meeting.invitee != ticket:
			frappe.throw(_("Only the invited participant can respond"), frappe.PermissionError)
		if meeting.status != "Requested":
			frappe.throw(_("This request has already been answered"))
		meeting.status = "Accepted" if action == "accept" else "Declined"
	elif action == "cancel":
		if ticket not in (meeting.requester, meeting.invitee):
			frappe.throw(_("Not your meeting"), frappe.PermissionError)
		meeting.status = "Cancelled"
	else:
		frappe.throw(_("Unknown action"))
	meeting.save(ignore_permissions=True)

	other_party = meeting.requester if ticket == meeting.invitee else meeting.invitee
	actor_name = frappe.db.get_value("Event Ticket", ticket, "attendee_name")
	enqueue_notification(
		[other_party],
		_("Meeting {0}").format(_(meeting.status).lower()),
		_("{0}: {1}").format(actor_name, _(meeting.status).lower()),
		{"type": "meeting", "name": meeting.name},
	)
	return meeting.status
