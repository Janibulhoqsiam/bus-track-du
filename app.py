import os
import re
import json
import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from flask import Flask, jsonify, Response

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False  # Ensure Unicode (e.g. Bangla) is not escaped


access_token="EAB4rQwZAdmgUBOZBfngIHoGXVR7IlokYqK0CxdTj7ZBml3PmBZAhp9xCzAsOFA8L6xw7lhWcrOZBzkdA1MEwOdqJqUfmTsC9SvBlf86bRhxUisroZA4NrzRs1QWU2TjRMviEbEvQoqCegRAyBlUAKHwqNvHUSMuI7Xh9qjAHeEG4ewXwlTwAn9EzZBxcSiKtLkDFfRjbODKpM5tx0tlfgZDZD"

# Replace with your actual credentials and URLs
LOGIN_URL = "https://www.du.banglatracking.com/app_userssign_me_in"
# Define the tracking URLs for the three different buses
TRACKING_URLS = {
    "1": "https://www.du.banglatracking.com/app_deviceslive_tracking/0862292054314174",
    "2": "https://www.du.banglatracking.com/app_deviceslive_tracking/0862292054293865",
    "3": "https://www.du.banglatracking.com/app_deviceslive_tracking/0862292054297585"
}
USERNAME = "2020113380"
PASSWORD = "trackmyback@321"

# Global variable to store the session
session = None

def login_and_get_session():
    """
    Logs into the tracking website and returns an authenticated session.
    """
    new_session = requests.Session()

    # First, load the login page to get the CSRF token and session cookies.
    login_page = new_session.get(LOGIN_URL)
    if login_page.status_code != 200:
        print("Failed to load login page")
        return None

    soup = BeautifulSoup(login_page.text, 'html.parser')
    csrf_token_tag = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    if not csrf_token_tag:
        print("Could not find CSRF token on login page")
        return None
    csrf_token = csrf_token_tag['value']
    print(f"CSRF Token extracted: {csrf_token}")

    # Build the login payload with the extracted CSRF token.
    login_payload = {
        "csrfmiddlewaretoken": csrf_token,
        "username": USERNAME,
        "password": PASSWORD
    }

    # Optional headers for a better chance of success
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": LOGIN_URL,
        "Origin": "https://www.du.banglatracking.com"
    }

    # Perform the login
    response = new_session.post(LOGIN_URL, data=login_payload, headers=headers)
    if response.status_code == 200 and "logout" in response.text.lower():
        print("Login successful!")
        return new_session
    else:
        print("Login failed!")
        return None

def get_valid_session():
    """
    Returns a valid session.
    If the global session is not set or is invalid, it logs in again.
    """
    global session
    if session is None:
        session = login_and_get_session()
    else:
        # Test if session is still valid by accessing one of the tracking pages.
        test_response = session.get(list(TRACKING_URLS.values())[0])
        if test_response.status_code != 200 or "login" in test_response.text.lower():
            print("Session expired or invalid. Logging in again...")
            session = login_and_get_session()
    return session

def get_bus_coordinates(tracking_url):
    """
    Uses a valid session to retrieve the tracking page for the given URL and extracts
    the first latitude and longitude from the embedded Google Maps iframe.
    """
    valid_session = get_valid_session()
    if not valid_session:
        return None, None

    response = valid_session.get(tracking_url)
    if response.status_code != 200:
        print("Failed to access tracking page")
        return None, None

    html_content = response.text

    # Use regex to extract the first lat-long pair from a Google Maps iframe URL.
    # The pattern looks for: https://maps.google.com/maps?q=latitude,longitude
    match = re.search(r'https://maps\.google\.com/maps\?q=([-\d.]+),([-\d.]+)', html_content)
    if not match:
        print("No coordinates found in the tracking page")
        return None, None

    latitude_str, longitude_str = match.groups()
    try:
        latitude = float(latitude_str)
        longitude = float(longitude_str)
        return latitude, longitude
    except Exception as e:
        print("Error converting coordinates to float:", e)
        return None, None

def reverse_geocode(lat, lon):
    """
    Converts latitude & longitude to a street address using Geopy's Nominatim.
    """
    geolocator = Nominatim(user_agent="bus_tracker_bot")
    location = geolocator.reverse((lat, lon), exactly_one=True)
    return location.address if location else "Unknown location"

@app.route("/track_bus/<bus_id>", methods=["GET"])
def track_bus(bus_id):
    # Validate bus_id and get the corresponding tracking URL
    if bus_id not in TRACKING_URLS:
        return jsonify({"error": "Invalid bus id"}), 400

    tracking_url = TRACKING_URLS[bus_id]
    lat, lon = get_bus_coordinates(tracking_url)
    if lat is None or lon is None:
        return jsonify({"error": "Could not fetch bus coordinates"}), 500

    address = reverse_geocode(lat, lon)

   
    google_maps_url = f"https://maps.google.com/maps?q={lat},{lon}"

    # Return address, and Google Maps link
    data = {"address": address, "google_maps_link": google_maps_url}
    
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype='application/json; charset=utf-8'
    )












@app.route("/webhook", methods=["GET"])
def verify_webhook():
    # Facebook sends a GET request to verify the webhook
    # Retrieve the `hub.mode`, `hub.challenge`, and `hub.verify_token` parameters
    mode = request.args.get("hub.mode")
    challenge = request.args.get("hub.challenge")
    verify_token = request.args.get("hub.verify_token")

    # Your verify token (use a string to verify the webhook)
    if verify_token == "janibul_mamibot_verify_token_420":
        return challenge, 200  # Respond with the challenge to complete the verification
    else:
        return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def handle_messages():
    data = request.get_json()
    
    # Facebook verifies the incoming message
    for entry in data.get("entry", []):
        for messaging_event in entry.get("messaging", []):
            sender_id = messaging_event.get("sender", {}).get("id")  # Sender ID
            message_text = messaging_event.get("message", {}).get("text")  # User's message

            # Check if the user asked for bus location
            if "bus" in message_text.lower():
                # Extract bus number from the message
                bus_id = re.search(r"bus (\d+)", message_text.lower())
                if bus_id:
                    bus_id = bus_id.group(1)
                    return_data = get_bus_location(bus_id)
                    send_message(sender_id, return_data)
                else:
                    send_message(sender_id, "Please specify the bus number (e.g., Bus 1, Bus 2, Bus 3).")
            else:
                send_message(sender_id, "Send 'bus 1', 'bus 2', or 'bus 3' to track the bus.")
    
    return "OK", 200











    def send_message(recipient_id, text):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.post(
        "https://graph.facebook.com/v14.0/me/messages",
        json=payload,
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"Failed to send message: {response.text}")







def get_bus_location(bus_id):
    if bus_id not in TRACKING_URLS:
        return "Invalid bus ID. Please provide a valid bus number."

    tracking_url = TRACKING_URLS[bus_id]
    lat, lon = get_bus_coordinates(tracking_url)
    if lat is None or lon is None:
        return "Could not fetch bus coordinates."

    address = reverse_geocode(lat, lon)
    google_maps_url = f"https://maps.google.com/maps?q={lat},{lon}"
    
    return f"The current location of Bus {bus_id}: {address}\n{google_maps_url}"

































@app.route('/', methods=['GET'])
def working():
    return "Working", 200    


if __name__ == "__main__":
    # Use the PORT environment variable set by Render
    port = int(os.getenv("PORT", 5000))  # Defaults to 5000 if PORT is not set
    app.run(host="0.0.0.0", port=port)    

