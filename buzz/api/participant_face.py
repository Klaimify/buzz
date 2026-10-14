import base64

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime

from buzz.api.participant_auth import complete_sign_in
from buzz.participants.credentials import get_participant_by_email
from buzz.participants.face import verify_faces
from buzz.participants.session import get_my_ticket

NOTICE_VERSION = "2026-10"
MAX_SELFIE_BYTES = 2 * 1024 * 1024


@frappe.whitelist()
def grant_consent() -> dict:
	"""Opt in to face sign-in. Requires a registration photo; email sign-in always remains available."""
	ticket = get_my_ticket()
	if not frappe.db.get_value("Event Ticket", ticket.name, "photo"):
		frappe.throw(_("No registration photo is on file, so face sign-in is not available."))

	consent = frappe.new_doc("Face Consent")
	consent.update({"ticket": ticket.name, "consented_on": now_datetime(), "notice_version": NOTICE_VERSION})
	consent.insert(ignore_permissions=True)  # participant acts on their own record only
	frappe.db.set_value("Event Ticket", ticket.name, "face_signin_enabled", 1)
	return {"enabled": True}


@frappe.whitelist()
def withdraw_consent() -> dict:
	ticket = get_my_ticket()
	consents = frappe.get_all(
		"Face Consent", filters={"ticket": ticket.name, "withdrawn_on": ("is", "not set")}, pluck="name"
	)
	for consent in consents:
		frappe.db.set_value("Face Consent", consent, "withdrawn_on", now_datetime())
	frappe.db.set_value("Event Ticket", ticket.name, "face_signin_enabled", 0)
	return {"enabled": False}


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@rate_limit(key="email", limit=5, seconds=600)
def sign_in_with_face(email: str, selfie_base64: str) -> dict:
	"""Face sign-in for opted-in participants. Fails with one generic message for every reason."""
	generic_error = _("Face sign-in failed. Please use your email instead.")
	participant = get_participant_by_email(email or "")
	if not participant:
		frappe.throw(generic_error, frappe.AuthenticationError)

	enabled, photo = frappe.db.get_value("Event Ticket", participant, ["face_signin_enabled", "photo"])
	if not enabled or not photo:
		frappe.throw(generic_error, frappe.AuthenticationError)

	selfie = base64.b64decode(selfie_base64, validate=True)
	if len(selfie) > MAX_SELFIE_BYTES:
		frappe.throw(generic_error, frappe.AuthenticationError)
	reference = frappe.get_doc("File", {"file_url": photo}).get_content()
	if isinstance(reference, str):
		reference = reference.encode()

	if not verify_faces(reference, selfie):
		frappe.throw(generic_error, frappe.AuthenticationError)
	return complete_sign_in(participant)
