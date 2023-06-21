import requests
import json
from datetime import datetime
from google.cloud import storage

def process_response(body):
    for action in body["actions"]:
        if action["action_id"] == "response_message":
            process_message(action, body["message"]["metadata"], body["user"]["username"])
            respond(body["response_url"])
        elif action["action_id"] == "response_button":
            process_button()
        else:
            return False
    return True

def process_message(action, metadata, user):
    response = metadata["event_payload"]
    response["message"] = action["value"]
    response["user"] = user
    response["responseTime"] = datetime.fromtimestamp(int(float(action["action_ts"]))).isoformat()
    if metadata["event_type"] == "monthly_report":
        write_to_gcs(response, "monthly_responses.jsonl", "monthly")
        return True
    elif metadata["event_type"] == "anomaly_report":
        write_to_gcs(response, "anomaly_responses.jsonl", "anomaly")
        return True
    else:
        return False
    return True

def process_button():
    return True

def write_to_gcs(payload, file, report_type):
    storage_client = storage.Client(project='geoott-gov-finops-cc-003')
    bucket = storage_client.bucket('nbcu-finops-data-repo')
    blob = bucket.blob(file)
    try:
        with blob.open("r") as f:
            contents = f.read()
    except:
        contents = ""
        print(f'{file} created')
    if report_type == "monthly":
        contents += json.dumps(payload) + '\n'
    elif report_type == "anomaly":
        contents += json.dumps(payload) + '\n'
    else:
        return False
    blob.upload_from_string(contents)
    return True

def respond(response_url):
    return True