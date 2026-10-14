from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from buzz.participants import push

GOOD_TOKEN = "ExponentPushToken[abc]"


class TestPush(FrappeTestCase):
	def test_token_validation(self):
		self.assertTrue(push.is_valid_expo_token(GOOD_TOKEN))
		self.assertTrue(push.is_valid_expo_token("ExpoPushToken[abc]"))
		self.assertFalse(push.is_valid_expo_token("abc"))
		self.assertFalse(push.is_valid_expo_token(""))
		self.assertFalse(push.is_valid_expo_token("ExponentPushToken[abc"))

	def test_tokens_are_sent_in_batches_of_100(self):
		tokens = [f"ExponentPushToken[{index}]" for index in range(250)]
		with patch.object(push, "make_post_request") as post:
			post.side_effect = lambda url, json: {"data": [{"status": "ok"} for _message in json]}
			sent = push.send_to_tokens(tokens, "Title", "Body")
		self.assertEqual(sent, 250)
		self.assertEqual([len(call.kwargs["json"]) for call in post.call_args_list], [100, 100, 50])

	def test_unregistered_devices_are_deleted(self):
		response = {
			"data": [
				{"status": "ok"},
				{"status": "error", "details": {"error": "DeviceNotRegistered"}},
			]
		}
		with (
			patch.object(push, "make_post_request", return_value=response),
			patch.object(push.frappe, "get_all", return_value=["device-2"]) as get_all,
			patch.object(push.frappe, "delete_doc") as delete_doc,
		):
			sent = push.send_to_tokens([GOOD_TOKEN, "ExponentPushToken[gone]"], "T", "B")
		self.assertEqual(sent, 1)
		self.assertEqual(get_all.call_args.kwargs["filters"], {"expo_token": ("in", ["ExponentPushToken[gone]"])})
		delete_doc.assert_called_once_with("Participant Device", "device-2", ignore_permissions=True)

	def test_request_failure_does_not_raise(self):
		with (
			patch.object(push, "make_post_request", side_effect=ConnectionError),
			patch.object(push.frappe, "log_error") as log_error,
		):
			self.assertEqual(push.send_to_tokens([GOOD_TOKEN], "T", "B"), 0)
		log_error.assert_called_once()

	def test_no_devices_means_no_request(self):
		with patch.object(push, "make_post_request") as post, patch.object(push.frappe, "get_all", return_value=[]):
			self.assertEqual(push.notify_tickets([], "T", "B"), 0)
			self.assertEqual(push.notify_tickets(["1"], "T", "B"), 0)
		post.assert_not_called()
