"""
Aman's Team — Reactivation SMS Agent
Flask app with scheduler + Twilio webhook
"""

from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import pytz
import random
import time
import os
import threading

app = Flask(__name__)

conversations = {}

EASTERN         = pytz.timezone("America/Toronto")
DELAY_MIN       = 45
DELAY_MAX       = 90
DAILY_LIMIT     = 50
SEND_HOUR_START = 9
SEND_HOUR_END   = 20


def is_sending_hours() -> bool:
    now = datetime.now(EASTERN)
    return SEND_HOUR_START <= now.hour < SEND_HOUR_END


def human_delay():
    delay = random.randint(DELAY_MIN, DELAY_MAX)
    print(f"[THROTTLE] Waiting {delay}s before next message...")
    time.sleep(delay)


def run_daily_campaign():
    if not is_sending_hours():
        print("[SCHEDULER] Outside sending hours, skipping.")
        return

    from lead_tracker import (load_leads, get_pending_leads, get_followup_leads,
                               update_lead_sent)
    from message_templates import get_initial_message, get_followup_message
    from sms_sender import send_sms

    df = load_leads()
    sent_count = 0

    for _, lead in get_followup_leads(df).iterrows():
        if sent_count >= DAILY_LIMIT:
            break
        phone   = str(lead["Phone (Formatted)"]).strip()
        message = get_followup_message(str(lead["First Name"]).strip())
        if send_sms(phone, message):
            update_lead_sent(phone, message)
            sent_count += 1
            if sent_count < DAILY_LIMIT:
                human_delay()

    for _, lead in get_pending_leads(df).iterrows():
        if sent_count >= DAILY_LIMIT:
            break
        phone        = str(lead["Phone (Formatted)"]).strip()
        first_name   = str(lead["First Name"]).strip()
        buyer_seller = str(lead.get("Buyer/Seller", "")).strip()
        fav_city     = str(lead.get("Favorite City", "")).strip()
        message      = get_initial_message(first_name, buyer_seller, fav_city)
        if send_sms(phone, message):
            update_lead_sent(phone, message)
            sent_count += 1
            if sent_count < DAILY_LIMIT:
                human_delay()

    print(f"[SCHEDULER] Done. Sent: {sent_count}")


def scheduler_loop():
    last_run_date = None
    while True:
        now = datetime.now(EASTERN)
        today = now.date()
        if now.hour == 10 and last_run_date != today:
            print(f"[SCHEDULER] Starting daily campaign at {now}")
            last_run_date = today
            try:
                run_daily_campaign()
            except Exception as e:
                print(f"[SCHEDULER ERROR] {e}")
        time.sleep(60 * 30)


def send_delayed_reply(to_number: str, ai_reply: str, delay_seconds: int):
    from sms_sender import send_sms
    print(f"[TYPING DELAY] Waiting {delay_seconds}s to simulate human typing...")
    time.sleep(delay_seconds)
    send_sms(to_number, ai_reply)


@app.route("/webhook/sms", methods=["POST"])
def sms_webhook():
    from lead_tracker import update_lead_reply, update_lead_optout
    from sms_sender import generate_ai_reply, classify_lead_temperature

    incoming_msg = request.form.get("Body", "").strip()
    from_number  = request.form.get("From", "").strip()
    resp         = MessagingResponse()

    print(f"[INCOMING] {from_number}: {incoming_msg}")

    if incoming_msg.upper() in ["STOP", "UNSUBSCRIBE", "CANCEL", "QUIT", "END"]:
        update_lead_optout(from_number)
        resp.message("You've been unsubscribed. You won't receive any more messages from us. Take care!")
        return str(resp)

    if from_number not in conversations:
        conversations[from_number] = []

    temperature = classify_lead_temperature(incoming_msg)
    update_lead_reply(from_number, incoming_msg, temperature)
    ai_reply = generate_ai_reply(conversations[from_number], incoming_msg)

    words = len(ai_reply.split())
    typing_delay = random.randint(20, 45) + (words // 5)

    reply_thread = threading.Thread(
        target=send_delayed_reply,
        args=(from_number, ai_reply, typing_delay)
    )
    reply_thread.daemon = True
    reply_thread.start()

    return str(resp)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running", "agent": "Aman Reactivation Bot"})


@app.route("/trigger", methods=["GET"])
def manual_trigger():
    thread = threading.Thread(target=run_daily_campaign)
    thread.daemon = True
    thread.start()
    return jsonify({"status": "campaign triggered"})


scheduler_thread = threading.Thread(target=scheduler_loop)
scheduler_thread.daemon = True
scheduler_thread.start()
print("[AGENT] Background scheduler started")
