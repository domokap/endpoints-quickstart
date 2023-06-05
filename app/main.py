# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import json
from urllib.parse import unquote
from flask import Flask
from flask import request
from google.cloud import storage

app = Flask(__name__)

@app.route('/echo', methods=['POST'])
def echo():
    """Return POST request body and write to GCS file."""
    result = request.get_data()
    if result is None:
       return 'No body provided.', 400
    storage_client = storage.Client(project='geoott-gov-finops-cc-003')
    bucket = storage_client.bucket('nbcu-finops-data-repo')
    blob = bucket.blob('echo_body.txt')
    blob.upload_from_string(result)
    return result, 200

@app.route('/finbot', methods=['POST'])
def finbotResponse():
    """Process POST request from Slack."""
    result = request.get_data()
    if result is None:
       return 'No body provided.', 400
    # decoded = unquote(bytes(result,"utf-8"))
    # response_json = json.loads(decoded[8:].replace("+"," "))
    # msg = response_json["actions"]
    storage_client = storage.Client(project='geoott-gov-finops-cc-003')
    bucket = storage_client.bucket('nbcu-finops-data-repo')
    blob = bucket.blob('finbot_response.txt')
    # blob.upload_from_string(msg)
    # return msg, 200
    blob.upload_from_string(str(unquote(result)))
    return result, 200

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
