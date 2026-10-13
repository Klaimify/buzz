import hashlib
import hmac
import secrets

import frappe
from frappe import _
from frappe.auth import LoginAttemptTracker
from frappe.utils import now_datetime

FIRST_ACTIVATION_LINK_SECONDS = 72 * 3600
LOGIN_LINK_SECONDS = 15 * 60
OTP_SECONDS = 10 * 60
OTP_MAX_ATTEMPTS = 5


def hash_value(value: str) -> str:
	return hashlib.sha256(value.encode()).hexdigest()


def get_participant_by_email(email: str) -> str | None:
	"""Newest enabled participant record for an email address."""
	participants = frappe.get_all(
		"Event Participant",
		filters={"email": email.strip().lower(), "status": ("!=", "Disabled")},
		pluck="name",
		order_by="creation desc",
		limit=1,
	)
	return participants[0] if participants else None


def issue_login_link_token(participant: str, first_activation: bool) -> str:
	"""Single-use token. Only its hash is stored, so a cache dump cannot be replayed."""
	token = secrets.token_urlsafe(32)
	ttl = FIRST_ACTIVATION_LINK_SECONDS if first_activation else LOGIN_LINK_SECONDS
	frappe.cache.set_value(f"participant_link:{hash_value(token)}", participant, expires_in_sec=ttl)
	return token


def consume_login_link_token(token: str) -> str:
	cache_key = f"participant_link:{hash_value(token)}"
	participant = frappe.cache.get_value(cache_key)
	if not participant:
		frappe.throw(_("This link has expired or was already used."), frappe.AuthenticationError)
	frappe.cache.delete_value(cache_key)
	return participant


def issue_email_otp(participant: str) -> str:
	otp_code = f"{secrets.randbelow(10**6):06d}"
	digest = hmac.new(frappe.local.site.encode(), f"{participant}:{otp_code}".encode(), "sha256").hexdigest()
	frappe.cache.set_value(f"participant_otp:{participant}", digest, expires_in_sec=OTP_SECONDS)
	return otp_code


def verify_email_otp(participant: str, otp_code: str) -> None:
	tracker = LoginAttemptTracker(
		key=f"participant_otp:{participant}",
		max_consecutive_login_attempts=OTP_MAX_ATTEMPTS,
		lock_interval=OTP_SECONDS,
	)
	if not tracker.is_user_allowed():
		frappe.throw(_("Too many attempts. Please try again later."), frappe.AuthenticationError)

	cache_key = f"participant_otp:{participant}"
	stored_digest = frappe.cache.get_value(cache_key)
	candidate = hmac.new(
		frappe.local.site.encode(), f"{participant}:{(otp_code or '').strip()}".encode(), "sha256"
	).hexdigest()
	if not stored_digest or not hmac.compare_digest(stored_digest, candidate):
		tracker.add_failure_attempt()
		frappe.throw(_("Invalid or expired code."), frappe.AuthenticationError)

	frappe.cache.delete_value(cache_key)
	tracker.add_success_attempt()


def ensure_user(participant_name: str) -> str:
	"""Create the passwordless Website User for a participant on first activation."""
	participant = frappe.get_doc("Event Participant", participant_name)
	if participant.user and frappe.db.exists("User", participant.user):
		return participant.user

	if not frappe.db.exists("User", participant.email):
		user = frappe.new_doc("User")
		user.update(
			{
				"email": participant.email,
				"first_name": participant.full_name,
				"user_type": "Website User",
				"send_welcome_email": 0,
				"enabled": 1,
			}
		)
		# Participants are created by the import pipeline, not by a logged-in desk user.
		user.insert(ignore_permissions=True)

	participant.db_set("user", participant.email)
	return participant.email


def mark_activated(participant_name: str) -> None:
	participant = frappe.db.get_value("Event Participant", participant_name, ["status"], as_dict=True)
	if participant.status in ("Imported", "Invited"):
		frappe.db.set_value(
			"Event Participant",
			participant_name,
			{"status": "Activated", "activated_on": now_datetime()},
		)


def issue_api_credentials(user: str) -> dict:
	"""Mobile session credentials. Note: signing in on a new device replaces the previous secret."""
	user_doc = frappe.get_doc("User", user)
	if not user_doc.api_key:
		user_doc.api_key = frappe.generate_hash(length=15)
	api_secret = frappe.generate_hash(length=15)
	user_doc.api_secret = api_secret
	user_doc.save(ignore_permissions=True)
	return {"authorization": f"token {user_doc.api_key}:{api_secret}", "user": user}
