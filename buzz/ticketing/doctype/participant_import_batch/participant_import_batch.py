# Copyright (c) 2026, Klaimify and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.csvutils import read_csv_content

from buzz.participants.importer import upsert_participants


class ParticipantImportBatch(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		created: DF.Int
		csv_file: DF.Attach | None
		disabled: DF.Int
		error_count: DF.Int
		error_log: DF.Code | None
		event: DF.Link
		mode: DF.Literal["CSV", "Frappe Sync", "API"]
		source_system: DF.Data
		status: DF.Literal["Draft", "Queued", "Running", "Done", "Failed"]
		unchanged: DF.Int
		updated: DF.Int
	# end: auto-generated types

	@frappe.whitelist()
	def start_import(self):
		if self.mode != "CSV" or not self.csv_file:
			frappe.throw(frappe._("Attach a CSV file to import."))
		self.db_set("status", "Queued")
		frappe.enqueue(run_csv_batch, queue="long", timeout=3600, batch=self.name)

	def record_summary(self, summary: dict):
		self.db_set(
			{
				"status": "Done",
				"created": summary["created"],
				"updated": summary["updated"],
				"unchanged": summary["unchanged"],
				"disabled": summary["disabled"],
				"error_count": len(summary["errors"]),
				"error_log": frappe.as_json(summary["errors"]),
			}
		)


def run_csv_batch(batch: str):
	batch_doc = frappe.get_doc("Participant Import Batch", batch)
	batch_doc.db_set("status", "Running")
	try:
		file_doc = frappe.get_doc("File", {"file_url": batch_doc.csv_file})
		table = read_csv_content(file_doc.get_content())
		headers = [str(header).strip().lower() for header in table[0]]
		rows = [dict(zip(headers, values, strict=False)) for values in table[1:] if any(values)]
		for row in rows:
			row["cancelled"] = str(row.get("cancelled") or "").strip().lower() in ("1", "yes", "true")
		summary = upsert_participants(batch_doc.event, batch_doc.source_system, rows)
		batch_doc.record_summary(summary)
	except Exception:
		batch_doc.db_set("status", "Failed")
		frappe.log_error(f"Participant import {batch} failed")
		raise
