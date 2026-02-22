"""
Aman's Team — Reactivation SMS Agent
Flask app with scheduler + Twilio webhook
"""

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import random
import time
import os

from config import DAILY_SEND_LIMIT, SEND_HOUR_START, SEND_HOUR_END
from lead_tracker import (load_leads, get_pending_leads, get_followup_leads,
                           update_lead_sent, update_lead_reply, update_lead_optout)
from message_templates import get_initial_message, get_followup_message
from sms_sender import send_sms, generate_ai_reply, classify_lead_temperature

app = Flask(__name__)

# In-memory conversation store {phone: [{"role":..,"content":..}]}
conversations = {}

EASTERN = pytz.timezone("America/Toronto")

# Throttle settings — random delay between messages to avoid spam flags
DELAY_MIN_SECONDS = 45
DELAY_MAX_SECONDS = 90


def is_sending_hours() -> bool:
    now = datetime.now(EASTERN)
    return SEND_HOUR_START <= now.hour < SEND_HOUR_END


def human_delay():
    """Wait a random amount of time between messages to mimic human sending."""
    delay = random.randint(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS)
    print(f"[THROTTLE] Waiting {delay}s before next message...")
    time.sleep(delay)


def run_daily_campaign():
    """Scheduled job — sends initial messages and follow-ups with human-like throttling."""
    if not is_sending_hours():
        print("[SCHEDULER] Outside sending hours, skipping.")
        return

    df = load_leads()
    sent_count = 0

    # 1. Send follow-ups first (leads with no reply after 3 days)
    followups = get_followup_leads(df)
    for _, lead in followups.iterrows():
        if sent_count >= DAILY_SEND_LIMIT:
            break
        phone = str(lead["Phone (Formatted)"]).strip()
        first_name = str(lead["First Name"]).strip()
        message = get_followup_message(first_name)
        if send_sms(phone, message):
            update_lead_sent(phone, message)
            sent_count += 1
            if sent_count < DAILY_SEND_LIMIT:
                human_delay()

    # 2. Send initial messages to new pending leads
    pending = get_pending_leads(df)
    for _, lead in pending.iterrows():
        if sent_count >= DAILY_SEND_LIMIT:
            break
        phone        = str(lead["Phone (Formatted)"]).strip()
        first_name   = str(lead["First Name"]).strip()
        buyer_seller = str(lead.get("Buyer/Seller", "")).strip()
        fav_city     = str(lead.get("Favorite City", "")).strip()
        message      = get_initial_message(first_name, buyer_seller, fav_city)
        if send_sms(phone, message):
            update_lead_sent(phone, message)
            sent_count += 1
            if sent_count < DAILY_SEND_LIMIT:
                human_delay()

    print(f"[SCHEDULER] Campaign run complete. Sent: {sent_count}")


@app.route("/webhook/sms", methods=["POST"])
def sms_webhook():
    """Twilio webhook — handles all incoming replies."""
    incoming_msg = request.form.get("Body", "").strip()
    from_number  = request.form.get("From", "").strip()
    resp         = MessagingResponse()

    print(f"[INCOMING] {from_number}: {incoming_msg}")

    # Handle opt-out
    if incoming_msg.upper() in ["STOP", "UNSUBSCRIBE", "CANCEL", "QUIT", "END"]:
        update_lead_optout(from_number)
        resp.message("You've been unsubscribed. You won't receive any more messages from us. Take care!")
        return str(resp)

    # Get or create conversation history
    if from_number not in conversations:
        conversations[from_number] = []

    # Classify temperature
    temperature = classify_lead_temperature(incoming_msg)

    # Update lead record
    update_lead_reply(from_number, incoming_msg, temperature)

    # Generate AI reply
    ai_reply = generate_ai_reply(conversations[from_number], incoming_msg)

    # Send reply back
    resp.message(ai_reply)
    return str(resp)


@app.route("/health", methods=["GET"])
def health():
    return {"status": "running", "agent": "Aman Reactivation Bot"}, 200


@app.route("/trigger", methods=["GET"])
def manual_trigger():
    """Manual trigger endpoint to kick off campaign instantly."""
    run_daily_campaign()
    return {"status": "campaign triggered"}, 200


if __name__ == "__main__":
    scheduler = BackgroundScheduler(timezone=EASTERN)
    # Run every day at 10am Eastern
    scheduler.add_job(run_daily_campaign, "cron", hour=10, minute=0)
    scheduler.start()
    print("[AGENT] Scheduler started — campaign runs daily at 10am ET")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
