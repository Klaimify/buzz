import frappe
from frappe.model.naming import make_autoname

CATEGORY_CODES = {
	"International Buyer": "B",
	"Domestic Buyer": "N",
	"Exhibitor Rep": "E",
	"Delegate": "D",
	"Speaker": "S",
	"Sponsor": "P",
	"Media": "M",
	"Staff": "F",
}


def generate_registration_id(event: str, ticket_type: str) -> str:
	"""Registration IDs look like IIRS27-B-00421: event prefix, category letter, running number."""
	event_prefix = frappe.db.get_value("Buzz Event", event, "route") or event
	event_prefix = "".join(char for char in str(event_prefix).upper() if char.isalnum())[:12]
	category = frappe.db.get_value("Event Ticket Type", ticket_type, "title")
	category_code = CATEGORY_CODES.get(category, "X")
	return make_autoname(f"{event_prefix}-{category_code}-.#####")
