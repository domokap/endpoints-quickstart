import json
import yaml
import subprocess
import time
from subprocess import Popen, PIPE
from google.cloud import storage


current_project = subprocess.run("gcloud config get-value project", shell=True, capture_output=True).stdout.decode().strip()
storage_client = storage.Client(project=current_project)
default_bucket = "nbcu-finops-data-repo"


# =============================================================================
# exec(open('update_secrets_async.py').read())
# =============================================================================


def update_finbot_secrets(bucket=default_bucket, function_blob="finbot_functions.json", team_blob="finbot_config.json"):
  print(f"Getting {function_blob}")
  functions = get_blob(bucket, function_blob)
  if functions is False: return
  print(f"Getting {team_blob}")
  teams = get_blob(bucket, team_blob)
  if teams is False: return
  print("Gathering function descriptions")
  descriptions = describe(functions)
  print("Compiling secrets")
  current_secrets  = {function:{secret["key"]:secret["secret"] for secret in description.get("secretEnvironmentVariables",{})} for function, description in descriptions.items()}
  expected_secrets = {function:get_expected_secrets(func_conf, teams) for function, func_conf in functions.items()}
  missing_secrets = {function:{k:v for k,v in expected_secrets[function].items() if (k,v) not in current_secrets[function].items()} for function in functions.keys()}
  commands = [f"gcloud functions deploy {function} --update-secrets='{secret_arg(missing_secrets[function])}' --trigger-topic='{func_conf['trigger-topic']}' --runtime=python310 --source='gs://{get_source(function,func_conf['region'])}' --entry-point='{func_conf['entry-point']}' --region='{func_conf['region']}'" for function, func_conf in functions.items() if missing_secrets[function] != {}]
  todo = len(commands); ticker = 0
  if todo == 0: print("No functions need updating"); return
  print("Updating ", end=""); print(*(i for i in functions if missing_secrets[i] != {}), sep=", ")
  running_cmds = [Popen(i, stdout=PIPE, stderr=PIPE, shell=True) for i in commands]
  while running_cmds:
    for cmd in running_cmds:
      retcode = cmd.poll()
      if retcode is not None:
        if retcode == 0:
          # print(cmd.stdout.read().decode())
          print("\r", "\x1b[2K", "Updated ", cmd.args.split()[3])
        else:
        # if retcode != 0:
          print(cmd.stderr.read().decode())
        running_cmds.remove(cmd)
        break
      else:
        time.sleep(.1)
      print("\r", "\x1b[2K", "{:.0%} ".format((todo-len(running_cmds))/todo), "."*(int(ticker%5)+1), end=""); ticker += 0.5
  print("\r", "\x1b[2K", "100% .....")
  print("Done")
  return


def get_blob(bucket=default_bucket, blob=None):
  bucket = storage_client.bucket(bucket)
  blob = bucket.blob(blob)
  try:
    with blob.open("r") as f:
      config = json.loads(f.read())
  except:
    print(f"No valid {blob.name} found")
    return False
  return config


# =============================================================================
# def describe(functions):
#   descriptions = {}
#   commands = [f"gcloud functions describe --region={func_conf['region']} {function}" for function, func_conf in functions.items()]
#   todo = len(commands); ticker = 0
#   running_cmds = [Popen(i, stdout=PIPE, stderr=PIPE, shell=True) for i in commands]
#   while running_cmds:
#     for cmd in running_cmds:
#       retcode = cmd.poll()
#       if retcode is not None:
#         if retcode == 0:
#           descriptions[cmd.args.split()[-1]] = yaml.safe_load(cmd.stdout.read().decode())
#         else:
#           print(cmd.stderr.read().decode())
#         running_cmds.remove(cmd)
#         break
#       else:
#         time.sleep(.1)
#       print("\r", "\x1b[2K", "{:.0%} ".format((todo-len(running_cmds))/todo), "."*(int(ticker%5)+1), end=""); ticker += 0.5
#   print("\r", "\x1b[2K", "100% .....")
#   return descriptions
# =============================================================================


def describe(functions):
  all_functions = json.loads(subprocess.run("gcloud functions list --filter='name~finbot' --format='json'", shell=True, capture_output=True).stdout.decode())
  all_descriptions = {function["name"].split("/")[-1]:function for function in all_functions}
  descriptions = {k:v for k,v in all_descriptions if k in functions}
  return descriptions


def get_source(function, region):
  buckets = storage_client.list_buckets(prefix='gcf-sources')
  bucket_str = [i.name for i in buckets if region in i.name][0]
  blob_times = {}
  for blob in storage_client.list_blobs(bucket_str, prefix=function):
    blob_times[blob.name] = blob.time_created
  latest_blob = [blob for blob,time in blob_times.items() if time == max([time for blob,time in blob_times.items()])][0]
  source = bucket_str + "/" + latest_blob
  return source


def get_expected_secrets(func_conf, teams):
  expected_secrets = {}
  for team_conf in teams.values():
    if func_conf["custom"] == False:
      if not any(i in func_conf["labels"] for i in team_conf["skip_reports"]):
        expected_secrets[team_conf["webhook_secret"]] = team_conf["secret_name"]
    else:
      if func_conf["custom"] in team_conf["custom_reports"]:
        expected_secrets[team_conf["webhook_secret"]] = team_conf["secret_name"]
  expected_secrets.update(func_conf["secrets"])
  return expected_secrets


def secret_arg(missing_secrets):
  arg = ""
  for k,v in missing_secrets.items():
    arg += f"{k}={v}:latest,"
  return arg[:-1]

