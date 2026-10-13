import frappe
from frappe import _
from frappe.utils import get_url, now_datetime

from buzz.participants.credentials import issue_login_link_token

DEFAULT_WAVE_SIZE = 250


def build_activation_link(token: str) -> str:
	app_link_base = frappe.conf.get("participant_app_link_base") or f"{get_url()}/participant-app"
	return f"{app_link_base}/activate?token={token}"


def send_invite_wave(event: str, wave_size: int = DEFAULT_WAVE_SIZE, resend: bool = False) -> int:
	"""Send invites to the next batch of participants. Call again for the next wave."""
	statuses = ["Not Invited", "Invited"] if resend else ["Not Invited"]
	participants = frappe.get_all(
		"Event Ticket",
		filters={"event": event, "docstatus": 1, "access_status": ("in", statuses)},
		fields=["name", "attendee_name", "attendee_email", "registration_id", "invite_count"],
		order_by="creation asc",
		limit=wave_size,
	)
	event_title = frappe.db.get_value("Buzz Event", event, "title")

	for participant in participants:
		token = issue_login_link_token(participant.name, first_activation=True)
		try:
			frappe.sendmail(
				recipients=[participant.attendee_email],
				subject=_("Your {0} app access").format(event_title),
				template="participant_invite",
				args={
					"full_name": participant.attendee_name,
					"registration_id": participant.registration_id,
					"event_title": event_title,
					"activation_link": build_activation_link(token),
				},
				reference_doctype="Event Ticket",
				reference_name=participant.name,
			)
		except Exception:
			frappe.log_error(f"Invite failed for {participant.name}")
			continue
		frappe.db.set_value(
			"Event Ticket",
			participant.name,
			{
				"access_status": "Invited",
				"invited_on": now_datetime(),
				"invite_count": participant.invite_count + 1,
			},
		)
	return len(participants)


@frappe.whitelist()
def enqueue_invite_wave(event: str, wave_size: int = DEFAULT_WAVE_SIZE, resend: bool = False):
	frappe.only_for(["System Manager", "Event Manager"])
	frappe.enqueue(
		"buzz.participants.invites.send_invite_wave",
		queue="long",
		event=event,
		wave_size=int(wave_size),
		resend=bool(int(resend)),
	)
