from frappe.tests.utils import FrappeTestCase

from buzz.participants.importer import compute_source_hash, normalise_phone, validate_row


class TestImporterHelpers(FrappeTestCase):
	def test_normalise_phone(self):
		self.assertEqual(normalise_phone("98765 43210"), "+919876543210")
		self.assertEqual(normalise_phone("+234 803 123 4567"), "+2348031234567")
		self.assertEqual(normalise_phone("00971501234567"), "+971501234567")
		self.assertEqual(normalise_phone(""), "")

	def test_source_hash_changes_with_data(self):
		base = {"full_name": "A", "email": "a@x.com", "category": "Delegate"}
		self.assertEqual(compute_source_hash(base), compute_source_hash(dict(base)))
		self.assertNotEqual(compute_source_hash(base), compute_source_hash({**base, "full_name": "B"}))

	def test_validate_row(self):
		self.assertIsNotNone(validate_row({"external_id": "1", "full_name": "A", "email": "", "category": "Delegate"}))
		self.assertIsNone(
			validate_row({"external_id": "1", "full_name": "A", "email": "a@x.com", "category": "Delegate"})
		)
