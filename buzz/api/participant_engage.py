import frappe
from frappe import _

from buzz.participants.qr import resolve_ticket
from buzz.participants.session import get_my_ticket, get_ticket_by_registration_id

LEAD_SCANNING_CATEGORIES = ("Exhibitor Rep", "Sponsor")
DIRECTORY_FIELDS = ["registration_id", "attendee_name", "organisation", "country", "ticket_type"]


@frappe.whitelist()
def get_directory(search: str | None = None, category: str | None = None, start: int = 0, page_length: int = 30):
	"""Attendee directory. Only participants who have not opted out; no email or phone is exposed."""
	ticket = get_my_ticket()
	filters = {"event": ticket.event, "docstatus": 1, "show_in_directory": 1}
	if category:
		filters["ticket_type"] = frappe.db.get_value(
			"Event Ticket Type", {"event": ticket.event, "title": category}
		)
	or_filters = None
	if search:
		like = f"%{search.strip()}%"
		or_filters = [["attendee_name", "like", like], ["organisation", "like", like], ["country", "like", like]]
	return frappe.get_all(
		"Event Ticket",
		filters=filters,
		or_filters=or_filters,
		fields=DIRECTORY_FIELDS,
		order_by="attendee_name asc",
		limit_start=int(start),
		limit_page_length=min(int(page_length), 100),
	)


@frappe.whitelist()
def set_directory_visibility(visible: int) -> dict:
	ticket = get_my_ticket()
	frappe.db.set_value("Event Ticket", ticket.name, "show_in_directory", 1 if int(visible) else 0)
	return {"visible": bool(int(visible))}


def get_category_title(ticket_type: str) -> str | None:
	return frappe.db.get_value("Event Ticket Type", ticket_type, "title")


@frappe.whitelist()
def save_lead(code: str, rating: int = 0, tags: str | None = None, note: str | None = None) -> dict:
	"""Exhibitor lead capture. `code` is a scanned badge token or a Registration ID. Scanning again updates the lead."""
	scanner = get_my_ticket()
	if get_category_title(scanner.ticket_type) not in LEAD_SCANNING_CATEGORIES:
		frappe.throw(_("Lead scanning is only available to exhibitors and sponsors"), frappe.PermissionError)

	scanned_name = resolve_ticket(code)
	scanned = frappe.db.get_value(
		"Event Ticket", scanned_name, ["event", "attendee_name", "organisation", "country"], as_dict=True
	)
	if scanned.event != scanner.event:
		frappe.throw(_("This badge belongs to a different event"))

	lead_name = frappe.db.get_value("Event Lead", {"scanner": scanner.name, "scanned": scanned_name})
	lead = frappe.get_doc("Event Lead", lead_name) if lead_name else frappe.new_doc("Event Lead")
	lead.update(
		{
			"event": scanner.event,
			"scanner": scanner.name,
			"scanned": scanned_name,
			"rating": max(0, min(int(rating), 5)),
			"tags": tags,
			"note": note,
		}
	)
	lead.save(ignore_permissions=True)  # scanner identity and category were verified above
	return {"lead": lead.name, "attendee_name": scanned.attendee_name, "organisation": scanned.organisation}


@frappe.whitelist()
def list_leads() -> list[dict]:
	scanner = get_my_ticket()
	leads = frappe.get_all(
		"Event Lead",
		filters={"scanner": scanner.name},
		fields=["scanned", "rating", "tags", "note", "modified"],
		order_by="modified desc",
	)
	people = {
		person.name: person
		for person in frappe.get_all(
			"Event Ticket",
			filters={"name": ("in", [lead.scanned for lead in leads])},
			fields=["name", "attendee_name", "organisation", "country", "attendee_email", "phone"],
		)
	}
	# Contact details are shared with the exhibitor only because they scanned this person's badge.
	return [
		{**lead, **{key: people[lead.scanned].get(key) for key in ("attendee_name", "organisation", "country", "attendee_email", "phone")}}
		for lead in leads
		if lead.scanned in people
	]


@frappe.whitelist()
def get_announcements() -> list[dict]:
	ticket = get_my_ticket()
	category = get_category_title(ticket.ticket_type)
	return frappe.get_all(
		"Participant Announcement",
		filters={"event": ticket.event},
		or_filters=[["audience", "in", ["", category]], ["audience", "is", "not set"]],
		fields=["name", "title", "body", "creation"],
		order_by="creation desc",
		limit_page_length=50,
	)


@frappe.whitelist()
def list_polls() -> list[dict]:
	ticket = get_my_ticket()
	polls = frappe.get_all(
		"Event Poll",
		filters={"event": ticket.event},
		fields=["name", "question", "options", "is_open"],
		order_by="creation desc",
	)
	votes = frappe.get_all(
		"Poll Vote",
		filters={"poll": ("in", [poll.name for poll in polls])},
		fields=["poll", "ticket", "choice"],
	)
	result = []
	for poll in polls:
		options = [option.strip() for option in (poll.options or "").splitlines() if option.strip()]
		poll_votes = [vote for vote in votes if vote.poll == poll.name]
		result.append(
			{
				"name": poll.name,
				"question": poll.question,
				"is_open": bool(poll.is_open),
				"my_choice": next((vote.choice for vote in poll_votes if vote.ticket == ticket.name), None),
				"options": [
					{"label": option, "votes": sum(1 for vote in poll_votes if vote.choice == option)}
					for option in options
				],
			}
		)
	return result


@frappe.whitelist()
def vote(poll: str, choice: str) -> dict:
	ticket = get_my_ticket()
	poll_doc = frappe.db.get_value("Event Poll", poll, ["event", "options", "is_open"], as_dict=True)
	if not poll_doc or poll_doc.event != ticket.event:
		frappe.throw(_("Poll not found"))
	if not poll_doc.is_open:
		frappe.throw(_("This poll is closed"))
	options = [option.strip() for option in (poll_doc.options or "").splitlines()]
	if choice not in options:
		frappe.throw(_("Invalid option"))
	if frappe.db.exists("Poll Vote", {"poll": poll, "ticket": ticket.name}):
		frappe.throw(_("You have already voted"))

	vote_doc = frappe.new_doc("Poll Vote")
	vote_doc.update({"poll": poll, "ticket": ticket.name, "choice": choice})
	vote_doc.insert(ignore_permissions=True)  # one vote per participant, verified above
	return {"voted": True}


@frappe.whitelist()
def ask_question(talk: str, question: str) -> dict:
	ticket = get_my_ticket()
	if frappe.db.get_value("Event Talk", talk, "event") != ticket.event:
		frappe.throw(_("Session not found"))
	question_doc = frappe.new_doc("Session Question")
	question_doc.update({"event": ticket.event, "talk": talk, "ticket": ticket.name, "question": question.strip()})
	question_doc.insert(ignore_permissions=True)  # participant's own question
	return {"question": question_doc.name}


@frappe.whitelist()
def list_questions(talk: str) -> list[dict]:
	ticket = get_my_ticket()
	return frappe.get_all(
		"Session Question",
		filters={"talk": talk, "event": ticket.event, "status": ("!=", "Hidden")},
		fields=["name", "question", "status", "creation"],
		order_by="creation desc",
	)
