import frappe
from frappe import _
from frappe.utils import now_datetime

from buzz.participants.push import is_valid_expo_token
from buzz.participants.session import get_my_ticket


@frappe.whitelist()
def register_device(expo_token: str, platform: str | None = None) -> dict:
	"""Store this device's Expo push token. A token seen on a new account moves to that account."""
	if not is_valid_expo_token(expo_token):
		frappe.throw(_("Invalid push token"))
	ticket = get_my_ticket()

	existing = frappe.db.get_value("Participant Device", {"expo_token": expo_token})
	if existing:
		frappe.db.set_value(
			"Participant Device",
			existing,
			{"ticket": ticket.name, "event": ticket.event, "platform": platform, "last_seen": now_datetime()},
		)
		return {"registered": True}

	device = frappe.new_doc("Participant Device")
	device.update(
		{
			"ticket": ticket.name,
			"event": ticket.event,
			"expo_token": expo_token,
			"platform": platform,
			"last_seen": now_datetime(),
		}
	)
	device.insert(ignore_permissions=True)  # participants have no desk permissions; scoped to their own ticket
	return {"registered": True}


@frappe.whitelist()
def unregister_device(expo_token: str) -> dict:
	ticket = get_my_ticket()
	for device in frappe.get_all("Participant Device", filters={"expo_token": expo_token, "ticket": ticket.name}, pluck="name"):
		frappe.delete_doc("Participant Device", device, ignore_permissions=True)
	return {"registered": False}
