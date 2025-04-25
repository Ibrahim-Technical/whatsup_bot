
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

# Global store
message_log_dict = {}
RUN apt-get update && apt-get install -y libsndfile1
# Load client configs
def load_client_config(phone_number):
    config_path = f"configs/{phone_number}.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "greeting": "👋 Welcome to our smart assistant!",
        "custom_commands": {}
    }

# Log handling
def update_message_log(message, phone, role):
    if phone not in message_log_dict:
        message_log_dict[phone] = [{"role": "system", "content": "You are a helpful assistant."}]
    message_log_dict[phone].append({"role": role, "content": message})
    return message_log_dict[phone]

def remove_last_message(phone):
    if phone in message_log_dict:
        message_log_dict[phone].pop()

# AI Response
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

# Audio processing
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

# Send WhatsApp message
def send_whatsapp_message(to, msg, phone_number_id):
    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": msg}
    }
    requests.post(url, headers=headers, json=data)

# Handle incoming messages
def handle_message(req_data):
    value = req_data["entry"][0]["changes"][0]["value"]
    message = value["messages"][0]
    from_number = message["from"]
    phone_number_id = value["metadata"]["phone_number_id"]
    config = load_client_config(from_number)

    if message["type"] == "text":
        msg_text = message["text"]["body"].strip().lower()

        # Check for custom command
        if msg_text in config["custom_commands"]:
            reply = config["custom_commands"][msg_text]
        elif msg_text in ["hi", "hello", "السلام عليكم", "هلا"]:
            reply = config["greeting"]
        else:
            reply = get_ai_response(msg_text, from_number)

    elif message["type"] == "audio":
        audio_id = message["audio"]["id"]
        url = get_media_url(audio_id)
        bytes_data = download_media(url)
        audio_data = convert_audio(bytes_data)
        lang = detect_language(from_number)
        text = recognize_audio(audio_data, lang)
        reply = get_ai_response(text, from_number)
    else:
        reply = "🤖 Sorry, I can only process text and audio messages right now."

    send_whatsapp_message(from_number, reply, phone_number_id)

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
        try:
            handle_message(request.get_json())
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            logging.error(f"Webhook error: {e}")
            return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True,
        use_reloader=False
    )

