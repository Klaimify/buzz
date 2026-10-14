import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from buzz.participants import credentials, whatsapp
from buzz.participants.importer import upsert_participants

GENERIC_RESPONSE = {"message": "If this email is registered, we have sent you a sign-in link and code."}


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@rate_limit(key="email", limit=3, seconds=3600)
def request_sign_in(email: str, channel: str = "email") -> dict:
	"""
	Send a 6-digit code (and magic link by email) through email or WhatsApp. Always answers the same
	way to avoid account enumeration. WhatsApp falls back to email when it cannot be delivered.
	"""
	if channel == "whatsapp" and not whatsapp.is_configured():
		frappe.throw(_("WhatsApp sign-in is not available. Please use email."))

	participant = credentials.get_participant_by_email(email or "")
	if not participant:
		return GENERIC_RESPONSE

	access_status = frappe.db.get_value("Event Ticket", participant, "access_status")
	token = credentials.issue_login_link_token(participant, access_status != "Activated")
	otp_code = credentials.issue_email_otp(participant)

	if channel == "whatsapp":
		frappe.enqueue(
			"buzz.participants.whatsapp.send_otp_with_fallback",
			participant=participant,
			otp_code=otp_code,
			link_token=token,
			queue="short",
		)
	else:
		frappe.enqueue(
			"buzz.participants.invites.send_sign_in_email",
			participant=participant,
			otp_code=otp_code,
			link_token=token,
			queue="short",
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
	details["category"] = frappe.db.get_value("Event Ticket Type", details.ticket_type, "title")
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
