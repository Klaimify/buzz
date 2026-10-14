import frappe
from frappe.tests.utils import FrappeTestCase

from buzz.participants import credentials


class TestSignInCredentials(FrappeTestCase):
	def test_otp_is_single_use(self):
		otp_code = credentials.issue_email_otp("otp-test-1")
		self.assertRegex(otp_code, r"^\d{6}$")
		credentials.verify_email_otp("otp-test-1", otp_code)
		with self.assertRaises(frappe.AuthenticationError):
			credentials.verify_email_otp("otp-test-1", otp_code)

	def test_wrong_otp_is_rejected(self):
		otp_code = credentials.issue_email_otp("otp-test-2")
		wrong_code = "000000" if otp_code != "000000" else "111111"
		with self.assertRaises(frappe.AuthenticationError):
			credentials.verify_email_otp("otp-test-2", wrong_code)

	def test_otp_locks_after_repeated_failures(self):
		otp_code = credentials.issue_email_otp("otp-test-3")
		wrong_code = "000000" if otp_code != "000000" else "111111"
		for _attempt in range(credentials.OTP_MAX_ATTEMPTS):
			with self.assertRaises(frappe.AuthenticationError):
				credentials.verify_email_otp("otp-test-3", wrong_code)
		with self.assertRaises(frappe.AuthenticationError):
			credentials.verify_email_otp("otp-test-3", otp_code)

	def test_login_link_is_single_use(self):
		token = credentials.issue_login_link_token("link-test-1", first_activation=False)
		self.assertEqual(credentials.consume_login_link_token(token), "link-test-1")
		with self.assertRaises(frappe.AuthenticationError):
			credentials.consume_login_link_token(token)

	def test_unknown_login_link_is_rejected(self):
		with self.assertRaises(frappe.AuthenticationError):
			credentials.consume_login_link_token("not-a-real-token")
