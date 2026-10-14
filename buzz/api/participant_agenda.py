import frappe
from frappe import _


@frappe.whitelist()
def get_agenda() -> dict:
	"""Schedule of the event the signed-in participant is registered for, grouped by day."""
	event = frappe.db.get_value("Event Ticket", {"user": frappe.session.user, "docstatus": 1}, "event")
	if not event:
		frappe.throw(_("No active registration found"), frappe.PermissionError)

	items = frappe.get_all(
		"Schedule Item",
		filters={"parent": event, "parenttype": "Buzz Event"},
		fields=["type", "talk", "track", "date", "start_time", "end_time", "description"],
		order_by="date asc, start_time asc",
	)
	talk_names = list({item.talk for item in items if item.talk})
	talks = {
		talk.name: talk
		for talk in frappe.get_all(
			"Event Talk", filters={"name": ("in", talk_names)}, fields=["name", "title", "description"]
		)
	}
	speaker_rows = frappe.get_all(
		"Talk Speaker",
		filters={"parent": ("in", talk_names), "parenttype": "Event Talk"},
		fields=["parent", "speaker"],
	)
	speaker_names = list({row.speaker for row in speaker_rows})
	speakers = {
		speaker.name: speaker
		for speaker in frappe.get_all(
			"Speaker Profile",
			filters={"name": ("in", speaker_names)},
			fields=["name", "display_name", "designation", "company"],
		)
	}
	speakers_by_talk: dict[str, list[dict]] = {}
	for row in speaker_rows:
		profile = speakers.get(row.speaker)
		if profile:
			speakers_by_talk.setdefault(row.parent, []).append(
				{"name": profile.display_name, "designation": profile.designation, "company": profile.company}
			)

	days: dict[str, list[dict]] = {}
	for item in items:
		talk = talks.get(item.talk)
		days.setdefault(str(item.date), []).append(
			{
				"type": item.type,
				"talk": item.talk,
				"title": talk.title if talk else (item.description or _("Break")),
				"description": talk.description if talk else None,
				"track": item.track,
				"start_time": str(item.start_time) if item.start_time else None,
				"end_time": str(item.end_time) if item.end_time else None,
				"speakers": speakers_by_talk.get(item.talk, []),
			}
		)
	return {"event": event, "days": [{"date": date, "items": entries} for date, entries in days.items()]}
