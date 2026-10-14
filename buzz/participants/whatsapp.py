import frappe
from frappe.integration.utils import make_post_request

from buzz.participants.invites import send_sign_in_email

GRAPH_API_URL = "https://graph.facebook.com/v21.0"


def is_configured() -> bool:
	config = frappe.conf.get("participant_whatsapp") or {}
	return all(config.get(key) for key in ("phone_number_id", "access_token", "template_name"))


def send_otp(phone: str, otp_code: str) -> None:
	"""
	Send the sign-in code through the WhatsApp Cloud API using an approved authentication template.
	Configure in site_config: participant_whatsapp = {"phone_number_id": ..., "access_token": ...,
	"template_name": ..., "language": "en"}. Authentication templates take the code as the body
	parameter and again as the copy-code button parameter.
	"""
	config = frappe.conf.get("participant_whatsapp") or {}
	make_post_request(
		f"{GRAPH_API_URL}/{config['phone_number_id']}/messages",
		headers={"Authorization": f"Bearer {config['access_token']}"},
		json={
			"messaging_product": "whatsapp",
			"to": phone.lstrip("+"),
			"type": "template",
			"template": {
				"name": config["template_name"],
				"language": {"code": config.get("language", "en")},
				"components": [
					{"type": "body", "parameters": [{"type": "text", "text": otp_code}]},
					{
						"type": "button",
						"sub_type": "url",
						"index": "0",
						"parameters": [{"type": "text", "text": otp_code}],
					},
				],
			},
		},
	)


def send_otp_with_fallback(participant: str, otp_code: str, link_token: str) -> None:
	"""Background job: WhatsApp first, email if WhatsApp fails so the participant is never locked out."""
	phone = frappe.db.get_value("Event Ticket", participant, "phone")
	try:
		if not phone:
			raise ValueError("no phone on file")
		send_otp(phone, otp_code)
	except Exception:
		frappe.log_error(f"WhatsApp OTP failed for {participant}")
		send_sign_in_email(participant, otp_code, link_token)
