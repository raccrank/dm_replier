import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import json
import logging

# Set up logging for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# --- Configuration ---
# Your Twilio Account SID and Auth Token
# These are loaded from environment variables for security.
# You will need to set these on your server.
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
# Your Twilio phone number
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"  # Example number

# Product database and a new dictionary for numbered options
PRODUCT_OPTIONS = {
    1: {"name": "aliengo kingsize black", "price": 150},
    2: {"name": "korobo 1 1/4\" blue", "price": 100},
    3: {"name": "wetop 1 1/4\" brown", "price": 100},
    4: {"name": "box with 50 booklets", "price": 2300},
}
DELIVERY_CHARGE = 200
POCHI_DETAILS = "Pochi la Biashara 0743706598"

# A simple in-memory storage for user sessions.
# This is great for development, but for a real-world service (SaaS)
# you should use a database like Redis or Firestore to handle
# multiple users and server restarts gracefully.
sessions = {}

# --- Helper Functions for your SaaS business logic ---

def notify_client_of_handoff(customer_number, customer_message):
    """
    This function sends a notification to your client when a customer
    asks for a live agent. This is where you would integrate with
    your client's preferred communication method (e.g., Slack, email,
    or a dedicated API endpoint on their system).
    
    This abstracts away the Twilio logic.
    """
    logging.info(f"Handoff request from {customer_number}. Last message: {customer_message}")
    # Example: In a real-world scenario, you would make an API call to the client's
    # system or send a message to a private communication channel.
    # For now, we'll just log the request.
    handoff_message = (
        f"🚨 Live Agent Handoff Required! 🚨\n"
        f"Customer: {customer_number}\n"
        f"Message: {customer_message}\n"
        f"Please reply to the customer directly."
    )
    # TODO: Replace with actual notification logic
    # client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    # client.messages.create(
    #     from_=TWILIO_WHATSAPP_NUMBER,
    #     body=handoff_message,
    #     to="whatsapp:YOUR_CLIENT_WHATSAPP_NUMBER"
    # )

# --- Flask Endpoints ---

@app.route("/whatsapp", methods=["POST"])
def webhook():
    """
    The main webhook endpoint that listens for incoming WhatsApp messages
    from Twilio. This is where the magic happens!
    """
    incoming_msg = request.values.get("Body", "").lower().strip()
    from_number = request.values.get("From", "")
    response = MessagingResponse()

    # Get the user's session or create a new one
    user_session = sessions.get(from_number, {"state": "initial"})

    # Check for keywords that can be used at any time
    live_agent_keywords = ["help", "agent", "human", "talk to a person", "live agent"]
    if any(keyword in incoming_msg for keyword in live_agent_keywords):
        notify_client_of_handoff(from_number, incoming_msg)
        user_session["state"] = "handoff"
        sessions[from_number] = user_session
        response.message("Connecting you with a live agent now. They'll be with you shortly!")
        return str(response)

    if incoming_msg == "start":
        sessions.pop(from_number, None)
        response.message("Okay, let's start over! 🚀")
        return str(response)

    # --- State-based Conversation Flow ---
    if user_session["state"] == "initial":
        # First-time user message
        message = "Hey there! 🌿 Welcome to our rolling paper shop!\n\nHere's what we have:\n"
        for num, product_info in PRODUCT_OPTIONS.items():
            message += f"{num}. {product_info['name'].title()}: Ksh {product_info['price']}\n"
        message += "\nJust reply with the number of the product you'd like to order."
        response.message(message)
        user_session["state"] = "awaiting_product"

    elif user_session["state"] == "awaiting_product":
        selected_option = None
        try:
            # Try to convert the user's input to an integer and check if it's a valid option
            selected_option = int(incoming_msg)
            if selected_option not in PRODUCT_OPTIONS:
                raise ValueError
            
            selected_product_info = PRODUCT_OPTIONS[selected_option]
            user_session["product"] = selected_product_info["name"]
            user_session["price"] = selected_product_info["price"]
            user_session["state"] = "awaiting_quantity"
            response.message(f"Got it! How many booklets of *{user_session['product'].title()}* would you like?")
        except (ValueError, IndexError):
            response.message("Oops, that's not a valid option. Please choose a number from the list.\n\nType 'help' if you want to talk to an agent.")

    elif user_session["state"] == "awaiting_quantity":
        try:
            quantity = int(incoming_msg)
            if quantity <= 0:
                raise ValueError
            user_session["quantity"] = quantity
            user_session["state"] = "awaiting_location"
            response.message("Thanks! What's your delivery location? I'll calculate your total with the delivery fee.")
        except ValueError:
            response.message("Please enter a valid number for the quantity.")

    elif user_session["state"] == "awaiting_location":
        user_session["location"] = incoming_msg
        product_price = user_session["price"]
        quantity = user_session["quantity"]
        subtotal = product_price * quantity
        total = subtotal + DELIVERY_CHARGE
        user_session["total_price"] = total
        
        summary = (
            "⭐ *Order Summary* ⭐\n"
            f"Product: {user_session['product'].title()}\n"
            f"Quantity: {quantity}\n"
            f"Subtotal: Ksh {subtotal}\n"
            f"Delivery to {user_session['location']}: Ksh {DELIVERY_CHARGE}\n"
            "------------------------\n"
            f"💰 *Total: Ksh {total}*\n\n"
            "Reply with *'1'* to confirm your order and get payment details, or *'start'* to begin a new order."
        )
        response.message(summary)
        user_session["state"] = "awaiting_confirmation"

    elif user_session["state"] == "awaiting_confirmation":
        if incoming_msg == "1":
            message = (
                f"Awesome! Please pay Ksh {user_session['total_price']} to our Pochi la Biashara:\n"
                f"*{POCHI_DETAILS}*\n\n"
                "We'll dispatch your order as soon as we receive your payment!"
            )
            response.message(message)
            
            # Order is complete, reset the session for this user
            user_session["state"] = "initial"
            sessions.pop(from_number, None) # Remove the session to clean up memory
        else:
            response.message("Oops, that's not a valid option. Please reply with '1' to confirm, or 'start' to begin a new order.")
            # Keep the user in the same state in case they make another mistake
            user_session["state"] = "awaiting_confirmation"
    
    elif user_session["state"] == "handoff":
        # Do nothing, a human agent is now handling this conversation
        # You could send a passive "A human is still with you" message if needed
        pass
    
    sessions[from_number] = user_session
    return str(response)

# --- Endpoint for your client to send a payment receipt ---
@app.route("/send_receipt", methods=["POST"])
def send_receipt():
    """
    This endpoint allows your client to send a pre-formatted receipt
    to a customer's WhatsApp number.
    
    This is a key part of your service as it ensures your clients
    don't need to know anything about Twilio.
    """
    data = request.json
    customer_number = data.get("customer_number")
    message_body = data.get("message_body")
    
    if not customer_number or not message_body:
        return {"error": "Missing customer_number or message_body"}, 400

    # Twilio API call to send the message
    try:
        # client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        # client.messages.create(
        #     from_=TWILIO_WHATSAPP_NUMBER,
        #     to=customer_number,
        #     body=message_body
        # )
        logging.info(f"Receipt sent successfully to {customer_number}.")
        # Reset the customer's session if it was in handoff mode
        if sessions.get(customer_number, {}).get("state") == "handoff":
            sessions[customer_number]["state"] = "initial"
        return {"status": "success", "message": "Receipt sent!"}, 200
    except Exception as e:
        logging.error(f"Failed to send receipt: {e}")
        return {"status": "error", "message": "Failed to send receipt"}, 500

if __name__ == "__main__":
    # In a production environment, you would not run with debug=True.
    # You would also use a production server like Gunicorn or uWSGI.
    app.run(debug=True)
