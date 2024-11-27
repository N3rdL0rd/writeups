import requests
import os

url = "https://api.mtishows.com/graphql"

query = """
query getBookingForCode($rehearsalCode: String!) {
  getBookingForCode(rehearsalCode: $rehearsalCode) {
    rehearsal_tracks {
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

variables = {
    "rehearsalCode": input("Rehearsal code: ")
}

headers = {
    "Content-Type": "application/json",
    "x-client-id": "1b882a3e-747b-4f00-87f9-2b455735203e",
    "x-platform-id": "72095991-8343-4c89-9f95-eee6f5340224"
}

response = requests.post(
    url,
    json={"query": query, "variables": variables},
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    data = data['data']['getBookingForCode']
    show = data['show']['name']
    print(f"Show: {show}")
    os.makedirs(show, exist_ok=True)
    for track in data['rehearsal_tracks']:
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

