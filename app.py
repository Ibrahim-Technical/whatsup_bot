from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/webhook", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "hello" in incoming_msg:
        msg.body("Hey there! How can I help you? 😊")
    elif "bye" in incoming_msg:
        msg.body("Goodbye! 👋 Have a great day.")
    elif "help" in incoming_msg:
        msg.body("You can say: hello, bye, or help.")
    else:
        msg.body("I didn’t understand that. Try: hello, bye, or help.")

    return str(resp)

if __name__ == "__main__":
    app.run(debug=True)
