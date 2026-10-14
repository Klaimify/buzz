import frappe
from frappe import _

try:
	import boto3
except ImportError:  # optional: only needed for the Rekognition verifier
	boto3 = None

SIMILARITY_THRESHOLD = 90


def verify_faces(reference_image: bytes, selfie_image: bytes) -> bool:
	"""
	Compare a selfie with the registration photo. A custom verifier can be set in hooks.py as
	participant_face_verifier = ["app.module.function"] (function(reference, selfie) -> bool);
	otherwise AWS Rekognition is used when `participant_face_aws` is set in site_config.
	"""
	for verifier_path in frappe.get_hooks("participant_face_verifier"):
		return bool(frappe.get_attr(verifier_path)(reference_image, selfie_image))

	aws_config = frappe.conf.get("participant_face_aws")
	if not aws_config or boto3 is None:
		frappe.throw(_("Face sign-in is not available. Please sign in with your email."))

	client = boto3.client(
		"rekognition",
		region_name=aws_config["region"],
		aws_access_key_id=aws_config["access_key"],
		aws_secret_access_key=aws_config["secret_key"],
	)
	response = client.compare_faces(
		SourceImage={"Bytes": reference_image},
		TargetImage={"Bytes": selfie_image},
		SimilarityThreshold=SIMILARITY_THRESHOLD,
	)
	return bool(response.get("FaceMatches"))
