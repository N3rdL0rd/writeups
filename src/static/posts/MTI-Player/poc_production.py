# /// script
# dependencies = [
#   "requests",
# ]
# ///

import requests
import os

HEADERS = {
    "x-platform-id": "bd6dbdd5-778d-4013-9820-3727d263e140",
    "x-client-id":   "1b882a3e-747b-4f00-87f9-2b455735203e",
    "x-device-id":   "79C87F0E-9237-5ABD-AA91-25F794E1F52E", # you can change this and x-device-desc, but avoid touching other headers
    "x-device-type": "Mac",
    "x-app-version": "1.2.1",
    "x-device-desc": "theatre-imac",
    "User-Agent":    "MTI%20Player/35 CFNetwork/1120 Darwin/19.0.0 (x86_64)"
}

query = """
query getBookingForCode($rehearsalCode: String!) {
  getBookingForCode(rehearsalCode: $rehearsalCode) {
    production_tracks {
      cue_number
      track_name
      time
      time_formatted
      location
      track_id
      __typename
    }
    show {
      name
      __typename
    }
    organization {
      name
      __typename
    }
    __typename
  }
}
"""

account = {
    "username": input("Username: "),
    "password": input("Password: ")
}

r = requests.post(
    "https://api.mtishows.com/signin",
    json=account,
    headers=HEADERS
)
token = r.json()['result']['token']

HEADERS['x-auth-token'] = token

response = requests.post(
    "https://api.mtishows.com/graphql",
    json={"query": query, "variables": {
        "rehearsalCode": input("Rehearsal code: ")
    }},
    headers=HEADERS
)

if response.status_code == 200:
    data = response.json()
    data = data['data']['getBookingForCode']
    show = data['show']['name']
    print(f"Show: {show}")
    os.makedirs(show, exist_ok=True)
    for track in data['production_tracks']:
        location_url = track['location']
        track_name = track['track_name']

        file_name = f"{track['cue_number']}. {track_name}.mp3"
        file_path = os.path.join(show, file_name)
        
        print(f"Downloading {track_name}...")
        try:
            file_response = requests.get(location_url, stream=True)
            if file_response.status_code == 200:
                with open(file_path, 'wb') as file:
                    for chunk in file_response.iter_content(chunk_size=1024):
                        if chunk:
                            file.write(chunk)
            else:
                print(f"Failed to download {track_name}: {file_response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error downloading {track_name}: {e}")
else:
    print("Failed to fetch data:", response.status_code, response.text)

