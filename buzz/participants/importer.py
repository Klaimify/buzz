import hashlib
import re

import frappe
from frappe import _
from frappe.utils import now_datetime, validate_email_address

SYNCED_FIELDS = ("full_name", "email", "phone", "organisation", "country", "category", "photo")  # hashed for change detection
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


def get_ticket_types_by_category(event: str, categories: set[str]) -> dict[str, str]:
	"""One unpublished, free ticket type per participant category per event, created on demand."""
	ticket_types = frappe.get_all(
		"Event Ticket Type", filters={"event": event}, fields=["name", "title"]
	)
	ticket_type_by_category = {row.title: row.name for row in ticket_types}
	for category in categories - set(ticket_type_by_category):
		ticket_type = frappe.new_doc("Event Ticket Type")
		ticket_type.update({"event": event, "title": category, "price": 0, "is_published": 0})
		ticket_type.insert()
		ticket_type_by_category[category] = ticket_type.name
	return ticket_type_by_category


def split_name(full_name: str) -> tuple[str, str]:
	first_name, _separator, last_name = full_name.partition(" ")
	return first_name, last_name


def upsert_participants(event: str, source_system: str, rows: list[dict]) -> dict:
	"""
	Idempotent import of registrations as submitted Event Tickets, keyed on
	(event, source_system, external_id). Unchanged rows are skipped using source_hash;
	cancelled source rows cancel the ticket (never deleted).
	"""
	existing_tickets = frappe.get_all(
		"Event Ticket",
		filters={"event": event, "source_system": source_system},
		fields=["name", "external_id", "source_hash", "docstatus"],
	)
	existing_by_external_id = {row.external_id: row for row in existing_tickets}

	summary = {"created": 0, "updated": 0, "unchanged": 0, "disabled": 0, "errors": []}
	cleaned_rows = []
	for raw_row in rows:
		row = clean_row(raw_row)
		error = validate_row(row)
		if error:
			summary["errors"].append({"external_id": row.get("external_id"), "error": error})
			continue
		cleaned_rows.append(row)

	ticket_type_by_category = get_ticket_types_by_category(
		event, {row["category"] for row in cleaned_rows if not row.get("cancelled")}
	)

	for row in cleaned_rows:
		external_id = str(row["external_id"])
		existing = existing_by_external_id.get(external_id)

		if row.get("cancelled"):
			if existing and existing.docstatus == 1:
				ticket = frappe.get_doc("Event Ticket", existing.name)
				ticket.flags.ignore_links = True
				ticket.cancel()
				summary["disabled"] += 1
			continue

		source_hash = compute_source_hash(row)
		first_name, last_name = split_name(row["full_name"])
		values = {
			"first_name": first_name,
			"last_name": last_name,
			"attendee_name": row["full_name"],
			"attendee_email": row["email"],
			"phone": row["phone"],
			"organisation": row.get("organisation"),
			"country": row.get("country"),
			"source_hash": source_hash,
		}
		if row.get("photo"):
			values["photo"] = row["photo"]

		if existing and existing.docstatus == 1:
			if existing.source_hash == source_hash:
				summary["unchanged"] += 1
				continue
			# Submitted tickets are updated in place; category changes are not synced automatically.
			frappe.db.set_value("Event Ticket", existing.name, values)
			summary["updated"] += 1
			continue

		ticket = frappe.new_doc("Event Ticket")
		ticket.update(
			{
				**values,
				"event": event,
				"ticket_type": ticket_type_by_category[row["category"]],
				"source_system": source_system,
				"external_id": external_id,
			}
		)
		ticket.flags.skip_ticket_email = True
		ticket.insert()
		ticket.submit()
		existing_by_external_id[external_id] = frappe._dict(
			name=ticket.name, external_id=external_id, source_hash=source_hash, docstatus=1
		)
		summary["created"] += 1

	summary["finished_on"] = str(now_datetime())
	return summary
