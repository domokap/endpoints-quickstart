import requests
import json
import copy
from datetime import datetime
from google.cloud import storage

def process_response(body):
    response = copy.deepcopy(body)
    for action in body["actions"]:
        if "response_message" in action["action_id"]:
            # if process_message(action, body["message"]["metadata"], body["user"]["username"]):
            #     respond(response, action)
            if respond(response, action):
                relay(response, action)
                process_message(action, body["message"]["metadata"], body["user"]["username"])
        elif "response_button" in action["action_id"]:
            process_button()
        else:
            return False
    return True

def process_message(action, metadata, user):
    if action["value"] is None:
        return False
    # response = metadata["event_payload"]
    # response = {k:v for k,v in metadata["event_payload"] if "response_message" not in k}
    response = {k:v for k,v in metadata["event_payload"].items() if k in ["team", "ids"]}
    response["message"] = action["value"]
    response["user"] = user
    response["responseTime"] = datetime.fromtimestamp(int(float(action["action_ts"]))).isoformat()
    if metadata["event_type"] == "monthly_report":
        write_to_gcs(response, "monthly_responses.jsonl", "monthly")
        return True
    elif metadata["event_type"] == "anomaly_report":
        acc_id = action["action_id"]
        account = acc_id[acc_id.index("/")+1:]
        response["ids"] = response["ids"][account]
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

def respond(response, action):
    payload = {
        "replace_original": True,
        "text": response["message"]["text"],
        "blocks": response["message"]["blocks"],
        "metadata": response["message"]["metadata"]
    }
    ack_block = {
        "type": "section",
        "text": {
    	    "type": "mrkdwn",
    	    "text": "*Response Received* :white_check_mark: Send extra context as required; view all responses in thread :arrow_down:"
        }
    }
    acc_id = action["action_id"]
    account = acc_id[acc_id.index("/")+1:]
    action_index = payload["blocks"].index(next(i for i in response["message"]["blocks"] if i["block_id"] == action["block_id"]))
    max_responses = 5
    payload["metadata"]["event_payload"][action["action_id"]] = payload["metadata"]["event_payload"].get(action["action_id"], 0) + 1
    num_responses = payload["metadata"]["event_payload"][action["action_id"]]
    if num_responses == 1:
        payload["blocks"].insert(action_index+1, ack_block)
    if num_responses > max_responses:
        reject_text = f":negative_squared_cross_mark: _Maximum number of responses ({max_responses}) received for_ `" + account + "`"
        payload["blocks"][action_index+1]["text"]["text"] = reject_text
    payload = json.dumps(payload)
    print(payload)
    print(requests.post(response["response_url"], json=json.loads(payload)).json())
    if num_responses > max_responses:
        return False
    return True

def relay(response, action):
    acc_id = action["action_id"]
    account = acc_id[acc_id.index("/")+1:]
    user = response["user"]["username"]
    time = datetime.fromtimestamp(int(float(action["action_ts"]))).isoformat()
    payload = {
        "replace_original": False,
        "text": f"""_Account:_ `{account}`\n_User: {user}_\n_Time: {time}_\n_Response: {action["value"]}_""",
        "response_type": "in_channel",
        "thread_ts": response["message"]["ts"]
    }
    payload = json.dumps(payload)
    print(payload)
    print(requests.post(response["response_url"], json=json.loads(payload)).json())
    return True