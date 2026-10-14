import frappe
from frappe.integration.utils import make_post_request

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_BATCH_SIZE = 100  # Expo accepts at most 100 messages per request
EXPO_TOKEN_PREFIXES = ("ExponentPushToken[", "ExpoPushToken[")


def is_valid_expo_token(token: str) -> bool:
	return bool(token) and token.startswith(EXPO_TOKEN_PREFIXES) and token.endswith("]")


def get_device_tokens(tickets: list[str]) -> list[str]:
	if not tickets:
		return []
	return frappe.get_all("Participant Device", filters={"ticket": ("in", tickets)}, pluck="expo_token")


def send_to_tokens(tokens: list[str], title: str, body: str, data: dict | None = None) -> int:
	"""Send one notification to many devices and drop tokens Expo reports as unregistered."""
	sent = 0
	for start in range(0, len(tokens), EXPO_BATCH_SIZE):
		batch = tokens[start : start + EXPO_BATCH_SIZE]
		messages = [
			{"to": token, "title": title, "body": body, "data": data or {}, "sound": "default"}
			for token in batch
		]
		try:
			response = make_post_request(EXPO_PUSH_URL, json=messages)
		except Exception:
			frappe.log_error("Expo push request failed")
			continue
		stale_tokens = []
		for token, result in zip(batch, response.get("data", []), strict=False):
			if result.get("status") == "ok":
				sent += 1
			elif (result.get("details") or {}).get("error") == "DeviceNotRegistered":
				stale_tokens.append(token)
		if stale_tokens:
			for device in frappe.get_all("Participant Device", filters={"expo_token": ("in", stale_tokens)}, pluck="name"):
				frappe.delete_doc("Participant Device", device, ignore_permissions=True)
	return sent


def notify_tickets(tickets: list[str], title: str, body: str, data: dict | None = None) -> int:
	return send_to_tokens(get_device_tokens(tickets), title, body, data)


def send_announcement(announcement: str) -> int:
	"""Push a Participant Announcement to everyone in its audience. Runs as a background job."""
	doc = frappe.db.get_value(
		"Participant Announcement", announcement, ["event", "title", "body", "audience"], as_dict=True
	)
	if not doc:
		return 0

	filters = {"event": doc.event, "docstatus": 1}
	if doc.audience:
		ticket_types = frappe.get_all(
			"Event Ticket Type", filters={"event": doc.event, "title": doc.audience}, pluck="name"
		)
		filters["ticket_type"] = ("in", ticket_types or [""])
	tickets = frappe.get_all("Event Ticket", filters=filters, pluck="name")
	return notify_tickets(tickets, doc.title, doc.body, {"type": "announcement", "name": announcement})


def on_announcement_created(doc, method=None):
	frappe.enqueue(
		"buzz.participants.push.send_announcement",
		announcement=doc.name,
		queue="short",
		enqueue_after_commit=True,
	)


def enqueue_notification(tickets: list[str], title: str, body: str, data: dict | None = None):
	frappe.enqueue(
		"buzz.participants.push.notify_tickets",
		tickets=tickets,
		title=title,
		body=body,
		data=data,
		queue="short",
		enqueue_after_commit=True,
	)
