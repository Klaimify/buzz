import hashlib
import re

import frappe
from frappe import _
from frappe.utils import now_datetime, validate_email_address

SYNCED_FIELDS = ("full_name", "email", "phone", "organisation", "country", "category", "photo")
REQUIRED_FIELDS = ("external_id", "full_name", "email", "category")


def normalise_email(email: str | None) -> str:
	return (email or "").strip().lower()


def normalise_phone(phone: str | None, default_country_code: str = "91") -> str:
	"""Return a best-effort E.164 number, or an empty string if nothing usable is given."""
	raw_phone = (phone or "").strip()
	if not raw_phone:
		return ""
	digits = re.sub(r"\D", "", raw_phone)
	if not digits:
		return ""
	if raw_phone.startswith("+"):
		return f"+{digits}"
	if digits.startswith("00"):
		return f"+{digits[2:]}"
	if len(digits) == 10:
		return f"+{default_country_code}{digits}"
	return f"+{digits}"


def compute_source_hash(row: dict) -> str:
	payload = "|".join(str(row.get(field) or "") for field in SYNCED_FIELDS)
	return hashlib.sha256(payload.encode()).hexdigest()


def clean_row(raw_row: dict) -> dict:
	row = {key: (value.strip() if isinstance(value, str) else value) for key, value in raw_row.items()}
	row["email"] = normalise_email(row.get("email"))
	row["phone"] = normalise_phone(row.get("phone"))
	return row


def validate_row(row: dict) -> str | None:
	"""Return an error message for an unusable row, otherwise None."""
	missing = [field for field in REQUIRED_FIELDS if not row.get(field)]
	if missing:
		return _("Missing: {0}").format(", ".join(missing))
	if not validate_email_address(row["email"]):
		return _("Invalid email")
	return None


def upsert_participants(event: str, source_system: str, rows: list[dict]) -> dict:
	"""
	Idempotent import keyed on (event, source_system, external_id).
	Unchanged rows are skipped using source_hash, cancelled rows become Disabled (never deleted).
	"""
	existing_participants = frappe.get_all(
		"Event Participant",
		filters={"event": event, "source_system": source_system},
		fields=["name", "external_id", "source_hash", "status"],
	)
	existing_by_external_id = {row.external_id: row for row in existing_participants}

	summary = {"created": 0, "updated": 0, "unchanged": 0, "disabled": 0, "errors": []}

	for raw_row in rows:
		row = clean_row(raw_row)
		error = validate_row(row)
		if error:
			summary["errors"].append({"external_id": row.get("external_id"), "error": error})
			continue

		external_id = str(row["external_id"])
		existing = existing_by_external_id.get(external_id)
		is_cancelled = bool(row.get("cancelled"))

		if existing and is_cancelled:
			if existing.status != "Disabled":
				frappe.db.set_value("Event Participant", existing.name, "status", "Disabled")
				summary["disabled"] += 1
			continue
		if is_cancelled:
			continue

		source_hash = compute_source_hash(row)
		if existing:
			if existing.source_hash == source_hash and existing.status != "Disabled":
				summary["unchanged"] += 1
				continue
			participant = frappe.get_doc("Event Participant", existing.name)
			participant.update({field: row.get(field) for field in SYNCED_FIELDS if field != "photo"})
			if row.get("photo"):
				participant.photo = row["photo"]
			participant.source_hash = source_hash
			if participant.status == "Disabled":
				participant.status = "Activated" if participant.activated_on else "Imported"
			participant.save()
			summary["updated"] += 1
			continue

		participant = frappe.new_doc("Event Participant")
		participant.update(
			{
				"event": event,
				"source_system": source_system,
				"external_id": external_id,
				"source_hash": source_hash,
				**{field: row.get(field) for field in SYNCED_FIELDS},
			}
		)
		participant.insert()
		existing_by_external_id[external_id] = frappe._dict(
			name=participant.name, external_id=external_id, source_hash=source_hash, status="Imported"
		)
		summary["created"] += 1

	summary["finished_on"] = str(now_datetime())
	return summary
