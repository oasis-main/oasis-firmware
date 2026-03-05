#File for all database functions
import sys

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

import requests
import orjson
import pyrebase

def initialize_user(RefreshToken):

    #app configuration information
    config = {
    "apiKey": "AIzaSyBPuJwU--0ZlvsbDV9LmKJdYIljwNwzmVk",
    "authDomain": "oasis-state-af548.firebaseapp.com",
    "databaseURL": "https://oasis-state-af548-default-rtdb.firebaseio.com/",
    "storageBucket": "oasis-state-af548.appspot.com"
    }

    firebase = pyrebase.initialize_app(config)
    # Get a reference to the auth service
    auth = firebase.auth()
    # Get a reference to the database service
    db = firebase.database()
    # Get a reference to the storage service
    storage = firebase.storage()
    #input by user on setup
    user = auth.refresh(RefreshToken)

    return user, db, storage

#gets new refresh token from firebase
def get_refresh_token(wak,email,password): #Depends on: 'requests', 'json'; Modifies: None
    print("Requesting refresh token...")
    sign_in_url = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key=" + wak
    sign_in_payload = orjson.dumps({"email": email, "password": password, "returnSecureToken": "true"})
    r = requests.post(sign_in_url, sign_in_payload)
    data = orjson.loads(r.content)
    print("Done.")
    return data["refreshToken"]

#get local_id and id_token from firebase
def get_local_credentials(wak,refresh_token): #Depends on: , 'requests'; Modifies: state variables,  cs.structs["access_config"].json
    print("Fetching local credentials...")
    refresh_url = "https://securetoken.googleapis.com/v1/token?key=" + wak
    refresh_payload = '{"grant_type": "refresh_token", "refresh_token": "%s"}' % refresh_token
    refresh_req = requests.post(refresh_url, data=refresh_payload)
    id_token = refresh_req.json()["id_token"]
    user_id = refresh_req.json()["user_id"]
    print("Done.")
    return id_token, user_id

def fetch_device_data(access_config):
    url = "https://oasis-state-af548-default-rtdb.firebaseio.com/"+str(access_config["local_id"])+"/"+str(access_config["device_name"])+".json?auth="+str(access_config["id_token"])
    result = requests.get(url)
    cloud_data = orjson.loads(result.content)
    return cloud_data

#modifies a firebase variable, now asynchroous
def patch_firebase(access_config,field,value): #Depends on: load_state(),'requests','json'; Modifies: database['field'], state variables
    data = orjson.dumps({field: value})
    url = "https://oasis-state-af548-default-rtdb.firebaseio.com/"+str(access_config["local_id"])+"/"+str(access_config["device_name"])+".json?auth="+str(access_config["id_token"])
    result = requests.patch(url,data)
    return result

def firebase_add_device(access_config,data): #Depends on: load_state(),'requests','json'; Modifies: database['field'], state variables
    data = orjson.dumps(data)
    url = "https://oasis-state-af548-default-rtdb.firebaseio.com/"+str(access_config["local_id"])+".json?auth="+str(access_config["id_token"])
    result = requests.patch(url,data)
    return result

#modifies a firebase variable, now asynchroous
def patch_firebase_dict(access_config, data): #Depends on: load_state(),'requests','json'; Modifies: database['field'], state variables
    data = orjson.dumps(data)
    url = "https://oasis-state-af548-default-rtdb.firebaseio.com/"+str(access_config["local_id"])+"/"+str(access_config["device_name"])+".json?auth="+str(access_config["id_token"])
    result = requests.patch(url,data)
    return result

#stores a file in firebase storage
def store_file(user, storage, path, device_name, filename):
    storage.child(user['userId'] + "/" + device_name + "/" + filename).put(path, user['idToken'])

