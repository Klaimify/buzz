from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from buzz.participants import whatsapp

CONFIG = {"phone_number_id": "123", "access_token": "secret", "template_name": "sign_in_code", "language": "en"}


class TestWhatsApp(FrappeTestCase):
	def test_is_configured(self):
		with patch.object(whatsapp.frappe, "conf", {"participant_whatsapp": CONFIG}):
			self.assertTrue(whatsapp.is_configured())
		with patch.object(whatsapp.frappe, "conf", {"participant_whatsapp": {"phone_number_id": "1"}}):
			self.assertFalse(whatsapp.is_configured())
		with patch.object(whatsapp.frappe, "conf", {}):
			self.assertFalse(whatsapp.is_configured())

	def test_send_otp_builds_authentication_template_payload(self):
		with (
			patch.object(whatsapp.frappe, "conf", {"participant_whatsapp": CONFIG}),
			patch.object(whatsapp, "make_post_request") as post,
		):
			whatsapp.send_otp("+919876543210", "123456")
		url = post.call_args.args[0]
		payload = post.call_args.kwargs["json"]
		self.assertTrue(url.endswith("/123/messages"))
		self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer secret"})
		self.assertEqual(payload["to"], "919876543210")
		self.assertEqual(payload["template"]["name"], "sign_in_code")
		self.assertEqual(payload["template"]["components"][0]["parameters"][0]["text"], "123456")

	def test_falls_back_to_email_when_whatsapp_fails(self):
		with (
			patch.object(whatsapp.frappe.db, "get_value", return_value="+919876543210"),
			patch.object(whatsapp, "send_otp", side_effect=RuntimeError),
			patch.object(whatsapp.frappe, "log_error"),
			patch.object(whatsapp, "send_sign_in_email") as send_email,
		):
			whatsapp.send_otp_with_fallback("1", "123456", "link-token")
		send_email.assert_called_once_with("1", "123456", "link-token")

	def test_falls_back_to_email_without_phone(self):
		with (
			patch.object(whatsapp.frappe.db, "get_value", return_value=None),
			patch.object(whatsapp, "send_otp") as send_otp,
			patch.object(whatsapp.frappe, "log_error"),
			patch.object(whatsapp, "send_sign_in_email") as send_email,
		):
			whatsapp.send_otp_with_fallback("1", "123456", "link-token")
		send_otp.assert_not_called()
		send_email.assert_called_once()

	def test_no_email_when_whatsapp_succeeds(self):
		with (
			patch.object(whatsapp.frappe.db, "get_value", return_value="+919876543210"),
			patch.object(whatsapp, "send_otp"),
			patch.object(whatsapp, "send_sign_in_email") as send_email,
		):
			whatsapp.send_otp_with_fallback("1", "123456", "link-token")
		send_email.assert_not_called()
