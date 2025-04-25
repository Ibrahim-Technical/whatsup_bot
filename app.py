
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import csv
import os
from datetime import datetime

app = Flask(__name__)

USERS_FILE = "users.csv"

def save_user(number, message):
    file_exists = os.path.isfile(USERS_FILE)
    with open(USERS_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "User", "Message"])
        writer.writerow([datetime.now().isoformat(), number, message])

@app.route("/webhook", methods=['POST'])
def webhook():
    incoming_msg = request.values.get('Body', '').strip().lower()
    from_number = request.values.get('From', '')
    resp = MessagingResponse()
    msg = resp.message()

    save_user(from_number, incoming_msg)

    if any(word in incoming_msg for word in ["hello", "hi", "هلا", "سلام"]):
        msg.body("👋 Hello! / أهلاً وسهلاً! كيف أقدر أساعدك؟")
    elif "help" in incoming_msg or "مساعدة" in incoming_msg:
        msg.body("🤖 You can say hello, info, or ask anything!\nيمكنك قول: هلا، مساعدة، أو اسألني أي شيء.")
    elif "info" in incoming_msg or "معلومات" in incoming_msg:
        msg.body("ℹ️ I'm a smart WhatsApp bot. Soon I'll be connected to AI!\nأنا بوت واتساب ذكي، وقريبًا سأكون مدعومًا بالذكاء الاصطناعي.")
    else:
        msg.body("❓ I didn’t understand that.\nلم أفهم ما قلته. جرب 'help' أو 'مساعدة'.")

    return str(resp)

if __name__ == "__main__":
    app.run(debug=True)
