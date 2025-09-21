gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=dd-ops-ocr-api-v2" --format="value(timestamp,severity,textPayload,jsonPayload.message)"
