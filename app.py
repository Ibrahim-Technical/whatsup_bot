
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if any(greet in incoming_msg for greet in ["hello", "hi", "هلا", "سلام"]):
        msg.body("👋 Hello! / مرحباً! كيف أقدر أساعدك؟")
    elif "help" in incoming_msg or "مساعدة" in incoming_msg:
        msg.body("🤖 You can say: hello, info, or ask anything!
يمكنك قول: هلا، مساعدة، أو اسألني أي شيء.")
    elif "info" in incoming_msg or "معلومات" in incoming_msg:
        msg.body("ℹ️ I'm a WhatsApp bot deployed on Railway!
أنا بوت واتساب مستضاف على منصة Railway.")
    else:
        msg.body("❓ I didn’t understand that.
لم أفهم ما قلته. جرب 'help' أو 'مساعدة'.")

    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
