import hashlib
import hmac

import frappe
from frappe import _
from frappe.utils.password import get_encryption_key

TOKEN_PREFIX = "B1"
SIGNATURE_LENGTH = 20


def sign(ticket: str, qr_version: int) -> str:
	message = f"{TOKEN_PREFIX}:{ticket}:{qr_version}".encode()
	return hmac.new(get_encryption_key().encode(), message, hashlib.sha256).hexdigest()[:SIGNATURE_LENGTH]


def build_token(ticket: str, qr_version: int) -> str:
	"""Signed badge token. Holds no personal data; bumping qr_version revokes older badges."""
	return f"{TOKEN_PREFIX}.{ticket}.{qr_version}.{sign(ticket, qr_version)}"


def resolve_ticket(code: str) -> str:
	"""Return the Event Ticket name for a scanned token or a typed Registration ID."""
	code = (code or "").strip()
	if code.startswith(f"{TOKEN_PREFIX}."):
		parts = code.split(".")
		if len(parts) != 4 or not parts[2].isdigit():
			frappe.throw(_("Invalid badge"))
		_prefix, ticket, qr_version, signature = parts
		if not hmac.compare_digest(signature, sign(ticket, int(qr_version))):
			frappe.throw(_("Invalid badge"))
		current_version = frappe.db.get_value("Event Ticket", ticket, "qr_version")
		if current_version is None or int(qr_version) != int(current_version):
			frappe.throw(_("This badge is no longer valid. Ask the help desk for a new one."))
		return ticket

	ticket = frappe.db.get_value("Event Ticket", {"registration_id": code, "docstatus": 1})
	if not ticket:
		frappe.throw(_("Registration not found"))
	return ticket
