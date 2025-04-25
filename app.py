
import io
import os
import json
import logging

import openai
import pydub
import requests
import soundfile as sf
import speech_recognition as sr
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables safely
openai.api_key = os.getenv("OPENAI_API_KEY")
whatsapp_token = os.getenv("WHATSAPP_TOKEN")
verify_token = os.getenv("VERIFY_TOKEN")

# Runtime data
message_log_dict = {}
usage_stats = {}

# Load previous message log if available
def load_message_log():
    global message_log_dict
    if os.path.exists("logs.json"):
        with open("logs.json", "r", encoding="utf-8") as f:
            message_log_dict = json.load(f)

def save_message_log():
    with open("logs.json", "w", encoding="utf-8") as f:
        json.dump(message_log_dict, f)

# Language detection (basic based on number)
def detect_language(phone_number):
    if phone_number.startswith("+966"):
        return "ar-SA"
    return "en-US"

# Media URL retrieval
def get_media_url(media_id):
    headers = {"Authorization": f"Bearer {whatsapp_token}"}
    url = f"https://graph.facebook.com/v16.0/{media_id}/"
    response = requests.get(url, headers=headers)
    logging.info(f"Media response: {response.json()}")
    return response.json()["url"]

# Media download
def download_media_file(media_url):
    headers = {"Authorization": f"Bearer {whatsapp_token}"}
    response = requests.get(media_url, headers=headers)
    return response.content

# Audio conversion
def convert_audio_bytes(audio_bytes):
    ogg_audio = pydub.AudioSegment.from_ogg(io.BytesIO(audio_bytes))
    ogg_audio = ogg_audio.set_sample_width(4)
    wav_bytes = ogg_audio.export(format="wav").read()
    audio_data, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="int32")
    sample_width = audio_data.dtype.itemsize
    return sr.AudioData(audio_data, sample_rate, sample_width)

# Speech recognition
def recognize_audio(audio_bytes, lang):
    recognizer = sr.Recognizer()
    return recognizer.recognize_google(audio_bytes, language=lang)

# Handle audio
def handle_audio_message(audio_id, from_number):
    lang = detect_language(from_number)
    audio_url = get_media_url(audio_id)
    audio_bytes = download_media_file(audio_url)
    audio_data = convert_audio_bytes(audio_bytes)
    audio_text = recognize_audio(audio_data, lang)
    return f"Please summarize the following message in its original language as bullet points: {audio_text}"

# Send WhatsApp response
def send_whatsapp_message(body, message):
    value = body["entry"][0]["changes"][0]["value"]
    phone_number_id = value["metadata"]["phone_number_id"]
    from_number = value["messages"][0]["from"]
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json",
    }
    url = f"https://graph.facebook.com/v15.0/{phone_number_id}/messages"
    data = {
        "messaging_product": "whatsapp",
        "to": from_number,
        "type": "text",
        "text": {"body": message},
    }
    response = requests.post(url, json=data, headers=headers)
    logging.info(f"WhatsApp message sent: {response.json()}")
    response.raise_for_status()

# Update log and stats
def update_message_log(message, phone_number, role):
    if phone_number not in message_log_dict:
        message_log_dict[phone_number] = [{"role": "system", "content": "You are a helpful assistant named WhatsBot."}]
    message_log_dict[phone_number].append({"role": role, "content": message})
    usage_stats[phone_number] = usage_stats.get(phone_number, 0) + 1
    save_message_log()
    return message_log_dict[phone_number]

def remove_last_message(phone_number):
    if phone_number in message_log_dict and message_log_dict[phone_number]:
        message_log_dict[phone_number].pop()

# OpenAI request
def make_openai_request(message, from_number):
    try:
        message_log = update_message_log(message, from_number, "user")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=message_log,
            temperature=0.7,
        )
        answer = response.choices[0].message.content
        update_message_log(answer, from_number, "assistant")
    except Exception as e:
        logging.error(f"OpenAI Error: {e}")
        remove_last_message(from_number)
        answer = "OpenAI API error. Please try again later."
    return answer

# Handle WhatsApp input
def handle_whatsapp_message(body):
    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    from_number = message["from"]
    if message["type"] == "text":
        message_body = message["text"]["body"]
    elif message["type"] == "audio":
        audio_id = message["audio"]["id"]
        message_body = handle_audio_message(audio_id, from_number)
    if message_body.lower() in ["reset", "إبدأ من جديد"]:
        message_log_dict[from_number] = []
        return send_whatsapp_message(body, "✅ Conversation reset.")
    response = make_openai_request(message_body, from_number)
    send_whatsapp_message(body, response)

# Webhook handler
def handle_message(request):
    body = request.get_json()
    logging.info(f"Request: {body}")
    try:
        if body.get("object") and body["entry"][0]["changes"][0]["value"].get("messages"):
            handle_whatsapp_message(body)
            return jsonify({"status": "ok"}), 200
        return jsonify({"status": "ignored"}), 404
    except Exception as e:
        logging.error(f"Handler error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Verification endpoint
def verify(request):
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token and mode == "subscribe" and token == verify_token:
        logging.info("WEBHOOK_VERIFIED")
        return challenge, 200
    return jsonify({"status": "error", "message": "Verification failed"}), 403

# Routes
@app.route("/", methods=["GET"])
def home():
    return "🤖 WhatsApp OpenAI Bot is running."

@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        return verify(request)
    return handle_message(request)

@app.route("/reset", methods=["GET"])
def reset():
    global message_log_dict
    message_log_dict = {}
    save_message_log()
    return "Message log reset!"

if __name__ == "__main__":
    load_message_log()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
