import frappe
from frappe.integration.utils import make_get_request

from buzz.participants.importer import upsert_participants

PAGE_SIZE = 500


def sync_registrations():
	"""
	Pull registrations from the registration Frappe instance configured in site_config:
	participant_sync = {"event": ..., "url": ..., "api_key": ..., "api_secret": ...,
	  "doctype": ..., "source_system": ..., "field_map": {"external_id": "name", "full_name": ..., ...},
	  "cancelled_field": "docstatus", "cancelled_value": 2}
	Runs from the scheduler; does nothing when not configured.
	"""
	config = frappe.conf.get("participant_sync")
	if not config:
		return

	field_map = config["field_map"]
	source_fields = sorted(set(field_map.values()) | {config.get("cancelled_field", "docstatus")})
	headers = {"Authorization": f"token {config['api_key']}:{config['api_secret']}"}
	rows = []
	limit_start = 0
	while True:
		response = make_get_request(
			f"{config['url'].rstrip('/')}/api/resource/{config['doctype']}",
			headers=headers,
			params={
				"fields": frappe.as_json(source_fields),
				"limit_start": limit_start,
				"limit_page_length": PAGE_SIZE,
			},
		)
		page = response.get("data", [])
		rows.extend(page)
		if len(page) < PAGE_SIZE:
			break
		limit_start += PAGE_SIZE

	cancelled_field = config.get("cancelled_field", "docstatus")
	cancelled_value = config.get("cancelled_value", 2)
	mapped_rows = []
	for source_row in rows:
		mapped_row = {target: source_row.get(source) for target, source in field_map.items()}
		mapped_row["cancelled"] = source_row.get(cancelled_field) == cancelled_value
		mapped_rows.append(mapped_row)

	summary = upsert_participants(config["event"], config.get("source_system", "frappe-registration"), mapped_rows)
	batch = frappe.new_doc("Participant Import Batch")
	batch.update({"event": config["event"], "source_system": config.get("source_system", "frappe-registration"), "mode": "Frappe Sync"})
	batch.insert(ignore_permissions=True)  # system-run sync, no desk user
	batch.record_summary(summary)
