from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Simple in-memory state
active_chats = {}
supervisors = ["+254700000001"]  # Replace with your number, can expand

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip().lower()
    from_number = request.values.get("From", "")

    resp = MessagingResponse()
    msg = resp.message()

    if incoming_msg == "#help":
        # Notify supervisor
        for sup in supervisors:
            print(f"Supervisor {sup} notified: Agent help requested from {from_number}")
        msg.body("🔔 An agent has been notified. Please wait to be connected.")
        active_chats[from_number] = "waiting_for_agent"

    elif incoming_msg == "#reply":
        if from_number in supervisors:
            # Supervisor replying to client
            target = request.values.get("WaId", "")
            msg.body("You are now live with the client. Type your reply.")
            active_chats[target] = "agent_live"
        else:
            msg.body("⚠️ Only agents can use #reply")

    elif incoming_msg == "#end":
        if from_number in supervisors:
            msg.body("✅ Chat session ended.")
            active_chats.clear()
        else:
            msg.body("⚠️ Only agents can end chats.")

    elif active_chats.get(from_number) == "agent_live":
        msg.body(f"👤 Agent: {incoming_msg}")

    else:
        msg.body("🤖 Auto-reply: Thanks for reaching out! Type #help if you need a live agent.")

    return str(resp)

if __name__ == "__main__":
    app.run(debug=True)
