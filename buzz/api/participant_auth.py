import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from buzz.participants import credentials
from buzz.participants.importer import upsert_participants
from buzz.participants.invites import build_activation_link

GENERIC_RESPONSE = {"message": "If this email is registered, we have sent you a sign-in link and code."}


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@rate_limit(key="email", limit=3, seconds=3600)
def request_sign_in(email: str) -> dict:
	"""Email a magic link and a 6-digit code. Always answers the same way to avoid account enumeration."""
	participant = credentials.get_participant_by_email(email or "")
	if not participant:
		return GENERIC_RESPONSE

	recipient, access_status = frappe.db.get_value(
		"Event Ticket", participant, ["attendee_email", "access_status"]
	)
	first_activation = access_status != "Activated"
	token = credentials.issue_login_link_token(participant, first_activation)
	otp_code = credentials.issue_email_otp(participant)

	frappe.enqueue(
		"frappe.sendmail",
		recipients=[recipient],
		subject=_("Your sign-in code"),
		message=_(
			"Your code is <b>{0}</b> (valid 10 minutes).<br><br>Or <a href='{1}'>open the app directly</a> (valid 15 minutes)."
		).format(otp_code, build_activation_link(token)),
		now=True,
	)
	return GENERIC_RESPONSE


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@rate_limit(key="token", limit=10, seconds=600)
def sign_in_with_link(token: str) -> dict:
	participant = credentials.consume_login_link_token(token)
	return complete_sign_in(participant)


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@rate_limit(key="email", limit=10, seconds=600)
def sign_in_with_otp(email: str, otp: str) -> dict:
	participant = credentials.get_participant_by_email(email or "")
	if not participant:
		frappe.throw(_("Invalid or expired code."), frappe.AuthenticationError)
	credentials.verify_email_otp(participant, otp)
	return complete_sign_in(participant)


def complete_sign_in(participant: str) -> dict:
	user = credentials.ensure_user(participant)
	credentials.mark_activated(participant)
	session = credentials.issue_api_credentials(user)
	details = frappe.db.get_value(
		"Event Ticket",
		participant,
		["registration_id", "attendee_name", "ticket_type", "organisation", "event", "face_signin_enabled", "show_in_directory"],
		as_dict=True,
	)
	return {
		**session,
		"participant": details,
		"is_staff": "Frontdesk Manager" in frappe.get_roles(user),
	}


@frappe.whitelist()
def upsert_registrations(event: str, source_system: str, rows: str) -> dict:
	"""Push endpoint for a registration system. Same idempotent upsert as CSV and sync."""
	frappe.only_for(["System Manager", "Event Manager"])
	return upsert_participants(event, source_system, frappe.parse_json(rows))
