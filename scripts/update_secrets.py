#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul  3 15:14:27 2023

@author: DKT06
"""

import json
import yaml
import subprocess
from google.cloud import storage


# storage_client = storage.Client(project='geoott-gov-finops-cc-003')
current_project = subprocess.run("gcloud config get-value project", shell=True, capture_output=True).stdout.decode().strip()
storage_client = storage.Client(project=current_project)
default_bucket = "nbcu-finops-data-repo"


init_script_command = "exec(open('update_secrets.py').read())"
ipython_init_script_command = "%run update_secrets.py"


def update_secrets(bucket=default_bucket, function_blob="finbot_functions.json", team_blob="finbot_config.json"):
# =============================================================================
#   functions = get_functions(bucket, function_blob)
#   teams = get_teams(bucket, team_blob)
# =============================================================================
  functions = get_blob(bucket, function_blob)
  teams = get_blob(bucket, team_blob)
  for function, func_conf in functions.items():
    region = func_conf["region"]
    description = describe(function, region)
    secrets = description.get("secretEnvironmentVariables", {})
    current_secrets = {i["key"]:i["secret"] for i in secrets}
    expected_secrets = get_expected_secrets(function, func_conf, teams)
    missing_secrets = {k:v for k,v in expected_secrets.items() if (k,v) not in current_secrets.items()}
    subprocess.run(f"gcloud functions deploy {function} --update-secrets='{secret_arg(missing_secrets)}' --trigger-topic='{func_conf['trigger-topic']}' --runtime=python310 --source='gs://{get_source(function,region)}' --entry-point='{func_conf['entry-point']}' --region='{region}'", shell=True)
  return True


# =============================================================================
# def get_functions(bucket=default_bucket, function_blob=default_function_blob):
#   bucket = storage_client.bucket(bucket)
#   blob = bucket.blob(function_blob)
#   try:
#     with blob.open("r") as f:
#       functions = json.loads(f.read())
#   except:
#     print(f"{function_blob} NOT FOUND")
#     return False
#   return functions
# =============================================================================


# =============================================================================
# def get_teams(bucket=default_bucket, team_blob=default_team_blob):
#   bucket = storage_client.bucket(bucket)
#   blob = bucket.blob(team_blob)
#   try:
#     with blob.open("r") as f:
#       teams = json.loads(f.read())
#   except:
#     print(f"{team_blob} NOT FOUND")
#     return False
#   return teams
# =============================================================================


def get_blob(bucket=default_bucket, blob=None):
  bucket = storage_client.bucket(bucket)
  blob = bucket.blob(blob)
  try:
    with blob.open("r") as f:
      config = json.loads(f.read())
  except:
    print(f"NO VALID {blob} FOUND")
    return False
  return config

def describe(function, region):
  description = subprocess.run(f"gcloud functions describe --region='{region}' {function}", shell=True, capture_output=True)
  func = yaml.safe_load(description.stdout.decode())
  return func


def get_source(function, region):
  buckets = storage_client.list_buckets(prefix='gcf-sources')
  bucket_str = [i.name for i in buckets if region in i.name][0]
  blob_times = {}
  for blob in storage_client.list_blobs(bucket_str, prefix=function):
    blob_times[blob.name] = blob.time_created
  latest_blob = [blob for blob,time in blob_times.items() if time == max([time for blob,time in blob_times.items()])][0]
  source = bucket_str + "/" + latest_blob
  return source


def get_expected_secrets(function, func_conf, teams):
  expected_secrets = {}
  for team, team_conf in teams.items():
    if not any(i in func_conf["labels"] for i in team_conf["skip_reports"]):
      expected_secrets[team_conf["webhook_secret"]] = team_conf["secret_name"]
  expected_secrets.update(func_conf["secrets"])
  return expected_secrets


def secret_arg(missing_secrets):
  arg = ""
  for k,v in missing_secrets.items():
    arg += f"{k}={v}:latest,"
  return arg[:-1]

