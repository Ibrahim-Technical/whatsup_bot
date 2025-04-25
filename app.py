import io
import os
import json
import logging
import openai
import pydub
import requests
import soundfile as sf
import speech_recognition as sr
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = "Razen"

# Vonage API credentials
VONAGE_API_KEY = '8b2f518b'
VONAGE_API_SECRET = 'UdYiHXY0jxDAkfWO'

# Global store for message logs
message_log_dict = {}

# Load client configurations from JSON
def load_client_config(phone_number):
    config_path = f"configs/{phone_number}.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "greeting": "👋 Welcome to our smart assistant!",
        "custom_commands": {}
    }

# Log handling for messages
def update_message_log(message, phone, role):
    if phone not in message_log_dict:
        message_log_dict[phone] = [{"role": "system", "content": "You are a helpful assistant."}]
    message_log_dict[phone].append({"role": role, "content": message})
    return message_log_dict[phone]

def remove_last_message(phone):
    if phone in message_log_dict:
        message_log_dict[phone].pop()

# AI Response from OpenAI
def get_ai_response(message, phone):
    try:
        log = update_message_log(message, phone, "user")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=log,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
        update_message_log(reply, phone, "assistant")
        return reply
    except Exception as e:
        logging.error(f"AI error: {e}")
        remove_last_message(phone)
        return "⚠️ Sorry, AI is unavailable right now."

# Audio processing for voice messages
def get_media_url(media_id):
    url = f"https://graph.facebook.com/v16.0/{media_id}/"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    return requests.get(url, headers=headers).json()["url"]

def download_media(url):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    return requests.get(url, headers=headers).content

def convert_audio(audio_bytes):
    audio = pydub.AudioSegment.from_ogg(io.BytesIO(audio_bytes)).set_sample_width(4)
    wav = audio.export(format="wav").read()
    data, rate = sf.read(io.BytesIO(wav), dtype="int32")
    return sr.AudioData(data, rate, data.dtype.itemsize)

def recognize_audio(audio_data, lang):
    return sr.Recognizer().recognize_google(audio_data, language=lang)

def detect_language(phone):
    if phone.startswith("+966"):
        return "ar-SA"
    return "en-US"

# Send WhatsApp message using Vonage Messages API
def send_whatsapp_message(to_number, from_number="14157386102"):
    # Vonage API URL for sending WhatsApp messages
    url = "https://messages-sandbox.nexmo.com/v1/messages"
    
    # Headers for the request
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    
    # Message data
    data = {
        "from": from_number,
        "to": to_number,
        "message_type": "text",
        "text": "This is a WhatsApp message sent from the Messages API",
        "channel": "whatsapp"
    }
    
    # Send POST request to Vonage API
    response = requests.post(url, headers=headers, auth=(VONAGE_API_KEY, VONAGE_API_SECRET), json=data)
    
    if response.status_code == 200:
        logging.info(f"Message sent successfully to {to_number}")
        logging.info(response.json())  # Print the response from Vonage
    else:
        logging.error(f"Failed to send message. Status code: {response.status_code}")
        logging.error(response.text)  # Print the error message if failed

# Handle incoming messages from Vonage
def handle_message(req_data):
    try:
        if "entry" not in req_data:
            logging.error(f"Invalid webhook data: {req_data}")
            return
        
        value = req_data["entry"][0].get("changes", [{}])[0].get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            logging.error(f"No messages found in the data: {req_data}")
            return

        message = messages[0]
        from_number = message.get("from", "")
        phone_number_id = value.get("metadata", {}).get("phone_number_id", "")

        config = load_client_config(from_number)

        if message.get("type") == "text":
            msg_text = message["text"].get("body", "").strip().lower()

            if msg_text in config["custom_commands"]:
                reply = config["custom_commands"][msg_text]
            elif msg_text in ["hi", "hello", "السلام عليكم", "هلا"]:
                reply = config["greeting"]
            else:
                reply = get_ai_response(msg_text, from_number)

        elif message.get("type") == "audio":
            audio_id = message["audio"].get("id", "")
            if audio_id:
                url = get_media_url(audio_id)
                bytes_data = download_media(url)
                audio_data = convert_audio(bytes_data)
                lang = detect_language(from_number)
                text = recognize_audio(audio_data, lang)
                reply = get_ai_response(text, from_number)
            else:
                reply = "🤖 Audio message is missing an ID."

        else:
            reply = "🤖 Sorry, I can only process text and audio messages right now."

        send_whatsapp_message(from_number, reply, phone_number_id)

    except Exception as e:
        logging.error(f"Error in handle_message: {e}")

# Flask routes
@app.route("/", methods=["GET"])
def home():
    return "🧠 WhatsApp AI Bot is Live"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN:
            return challenge, 200
        return "Unauthorized", 403

    elif request.method == "POST":
        logging.info(f"Full request body: {request.data}")
        
        if request.content_type == 'application/json':
            request_data = request.get_json()
            logging.info(f"Received JSON data: {request_data}")
        elif request.content_type == 'application/x-www-form-urlencoded':
            request_data = json.loads(request.form.get('payload', '{}'))
            logging.info(f"Received form data: {request_data}")
        else:
            logging.error(f"Unsupported Content-Type: {request.content_type}")
            return jsonify({"error": "Unsupported Media Type"}), 415
        
        try:
            handle_message(request_data)
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            logging.error(f"Webhook error: {e}")
            return jsonify({"error": str(e)}), 500

# Delivery receipt route (DLR)
@app.route("/delivery", methods=["POST"])
def delivery():
    delivery_data = request.get_json()  # Assuming JSON format
    logging.info(f"Delivery receipt: {delivery_data}")
    return jsonify({"status": "received"}), 200

# Inbound SMS route
@app.route("/inbound", methods=["POST"])
def inbound_sms():
    data = request.form
    from_number = data.get('msisdn')  # The sender's phone number
    text_message = data.get('text')   # The message content
    logging.info(f"Received SMS from {from_number}: {text_message}")
    return jsonify({"status": "received"}), 200

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True,
        use_reloader=False
    )
