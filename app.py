"""
Aman's Team — Reactivation SMS Agent
Flask app with scheduler + Twilio webhook + Dashboard
"""

from flask import Flask, request, jsonify, render_template_string, session, redirect
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import pytz
import random
import time
import os
import threading
import pandas as pd

app = Flask(__name__)
app.secret_key = os.environ.get("DASHBOARD_SECRET", "aman-royal-lepage-2024")

# In-memory conversation store {phone: [{"role":..,"content":..}]}
conversations = {}

# Campaign pause state
campaign_paused = False

EASTERN         = pytz.timezone("America/Toronto")
DELAY_MIN       = 45
DELAY_MAX       = 90
DAILY_LIMIT     = 50
SEND_HOUR_START = 9
SEND_HOUR_END   = 20
DASHBOARD_PASS  = os.environ.get("DASHBOARD_PASSWORD", "aman2024")
SECRET_PATH     = os.environ.get("DASHBOARD_PATH", "xK9mP2qR")
failed_attempts = {}   # {ip: {"count": n, "locked_until": float_timestamp}}
MAX_ATTEMPTS    = 5
LOCKOUT_MINS    = 15


def is_sending_hours() -> bool:
    now = datetime.now(EASTERN)
    return SEND_HOUR_START <= now.hour < SEND_HOUR_END


def human_delay():
    delay = random.randint(DELAY_MIN, DELAY_MAX)
    print(f"[THROTTLE] Waiting {delay}s before next message...")
    time.sleep(delay)


def run_daily_campaign():
    global campaign_paused
    if campaign_paused:
        print("[SCHEDULER] Campaign is paused, skipping.")
        return
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
        if sent_count >= DAILY_LIMIT or campaign_paused:
            break
        phone   = str(lead["Phone (Formatted)"]).strip()
        message = get_followup_message(str(lead["First Name"]).strip())
        if send_sms(phone, message):
            update_lead_sent(phone, message)
            sent_count += 1
            if sent_count < DAILY_LIMIT:
                human_delay()

    for _, lead in get_pending_leads(df).iterrows():
        if sent_count >= DAILY_LIMIT or campaign_paused:
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


# ─── DASHBOARD AUTH ───────────────────────────────────────────────────────────

@app.route(f"/{SECRET_PATH}/login", methods=["GET", "POST"])
def login():
    ip    = request.remote_addr
    entry = failed_attempts.get(ip, {"count": 0, "locked_until": 0.0})

    # Check if locked out
    if entry["locked_until"] > time.time():
        mins_left = int((entry["locked_until"] - time.time()) / 60) + 1
        return render_template_string(
            LOGIN_HTML,
            error=f"Too many failed attempts. Try again in {mins_left} minute(s)."
        )

    error = ""
    if request.method == "POST":
        if request.form.get("password") == DASHBOARD_PASS:
            failed_attempts.pop(ip, None)   # reset on success
            session["logged_in"] = True
            return redirect(f"/{SECRET_PATH}/")
        else:
            entry["count"] = entry.get("count", 0) + 1
            if entry["count"] >= MAX_ATTEMPTS:
                entry["locked_until"] = time.time() + (LOCKOUT_MINS * 60)
                entry["count"] = 0
                error = f"Too many failed attempts. Locked for {LOCKOUT_MINS} minutes."
            else:
                left = MAX_ATTEMPTS - entry["count"]
                error = f"Wrong password. {left} attempt(s) remaining before lockout."
            failed_attempts[ip] = entry

    return render_template_string(LOGIN_HTML, error=error)


@app.route(f"/{SECRET_PATH}/logout")
def logout():
    session.clear()
    return redirect(f"/{SECRET_PATH}/login")


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(f"/{SECRET_PATH}/login")
        return f(*args, **kwargs)
    return decorated


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@app.route("/")
def root():
    """Blank root — hides the fact that a dashboard exists."""
    return "<html><body></body></html>", 200


@app.route(f"/{SECRET_PATH}/")
@login_required
def dashboard():
    return render_template_string(DASHBOARD_HTML, secret_path=SECRET_PATH)


# ─── API ROUTES ───────────────────────────────────────────────────────────────

@app.route("/api/stats")
@login_required
def api_stats():
    from lead_tracker import load_leads, LEADS_FILE
    try:
        df = load_leads()
        total      = len(df)
        sent       = len(df[df["SMS Status"] == "Sent"])
        pending    = len(df[df["SMS Status"] == "Pending"])
        replied    = len(df[df["Reply Received"] == "Yes"])
        hot        = len(df[df["Lead Temperature"] == "Hot"])
        warm       = len(df[df["Lead Temperature"] == "Warm"])
        opted_out  = len(df[df["SMS Status"] == "Opted Out"])
        return jsonify({
            "total": total, "sent": sent, "pending": pending,
            "replied": replied, "hot": hot, "warm": warm,
            "opted_out": opted_out, "paused": campaign_paused
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/leads")
@login_required
def api_leads():
    from lead_tracker import load_leads
    try:
        df = load_leads()
        search = request.args.get("search", "").lower()
        filter_temp = request.args.get("filter", "all")

        if search:
            mask = (
                df["First Name"].astype(str).str.lower().str.contains(search) |
                df["Last Name"].astype(str).str.lower().str.contains(search) |
                df["Phone (Formatted)"].astype(str).str.contains(search)
            )
            df = df[mask]

        if filter_temp == "hot":
            df = df[df["Lead Temperature"] == "Hot"]
        elif filter_temp == "warm":
            df = df[df["Lead Temperature"] == "Warm"]
        elif filter_temp == "cold":
            df = df[df["Lead Temperature"] == "Cold"]
        elif filter_temp == "pending":
            df = df[df["SMS Status"] == "Pending"]
        elif filter_temp == "replied":
            df = df[df["Reply Received"] == "Yes"]

        df = df.fillna("")
        leads = df[[
            "First Name", "Last Name", "Phone (Formatted)",
            "Buyer/Seller", "SMS Status", "SMS Sent At",
            "Reply Received", "Reply Text", "Lead Temperature",
            "Favorite City", "Pipeline Stage"
        ]].to_dict(orient="records")

        return jsonify({"leads": leads, "total": len(leads)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversation/<path:phone>")
@login_required
def api_conversation(phone):
    history = conversations.get(phone, [])
    from lead_tracker import load_leads
    try:
        df = load_leads()
        df["Phone (Formatted)"] = df["Phone (Formatted)"].astype(str).str.strip()
        lead_row = df[df["Phone (Formatted)"] == phone.strip()]
        initial_msg = ""
        reply_text  = ""
        if not lead_row.empty:
            initial_msg = str(lead_row.iloc[0].get("SMS Message Sent", ""))
            reply_text  = str(lead_row.iloc[0].get("Reply Text", ""))
        return jsonify({
            "history": history,
            "initial_message": initial_msg,
            "reply_text": reply_text
        })
    except Exception as e:
        return jsonify({"history": history, "initial_message": "", "reply_text": ""})


@app.route("/api/reply", methods=["POST"])
@login_required
def api_manual_reply():
    from sms_sender import send_sms
    from lead_tracker import update_lead_reply
    data    = request.json
    phone   = data.get("phone", "")
    message = data.get("message", "")
    if not phone or not message:
        return jsonify({"error": "Phone and message required"}), 400
    if phone not in conversations:
        conversations[phone] = []
    conversations[phone].append({"role": "assistant", "content": message})
    success = send_sms(phone, message)
    return jsonify({"success": success})


@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload_leads():
    from lead_tracker import load_leads, LEADS_FILE, SHEET_NAME
    from openpyxl import load_workbook
    import io

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    try:
        new_df = pd.read_excel(io.BytesIO(file.read()))

        # Normalize column names
        col_map = {
            "first name": "First Name", "last name": "Last Name",
            "phone": "Phone (Formatted)", "cell phone": "Phone (Formatted)",
            "email": "Email", "email address": "Email",
            "buyer/seller": "Buyer/Seller", "city": "Favorite City",
            "notes": "Notes"
        }
        new_df.columns = [col_map.get(c.lower().strip(), c) for c in new_df.columns]

        # Format phone numbers
        def fmt_phone(p):
            if pd.isna(p): return ""
            n = str(p).strip().replace("-","").replace("(","").replace(")","").replace(" ","").replace("+","")
            if len(n) == 10: return f"+1{n}"
            elif len(n) == 11 and n.startswith("1"): return f"+{n}"
            return f"+{n}"

        if "Phone (Formatted)" in new_df.columns:
            new_df["Phone (Formatted)"] = new_df["Phone (Formatted)"].apply(fmt_phone)

        # Load existing leads and deduplicate
        existing_df = load_leads()
        existing_phones = set(existing_df["Phone (Formatted)"].astype(str).str.strip())
        new_df = new_df[~new_df["Phone (Formatted)"].isin(existing_phones)]

        if new_df.empty:
            return jsonify({"added": 0, "message": "No new leads — all duplicates"})

        # Add tracking columns
        new_df["SMS Status"]          = "Pending"
        new_df["SMS Sent At"]         = ""
        new_df["SMS Message Sent"]    = ""
        new_df["Reply Received"]      = "No"
        new_df["Reply Text"]          = ""
        new_df["Lead Temperature"]    = ""
        new_df["Follow Up Required"]  = ""
        new_df["Agent Notes"]         = ""

        # Append to Excel
        wb = load_workbook(LEADS_FILE)
        ws = wb[SHEET_NAME]
        headers = [cell.value for cell in ws[1]]

        for _, row in new_df.iterrows():
            new_row = []
            for h in headers:
                val = row.get(h, "")
                new_row.append("" if pd.isna(val) else val)
            ws.append(new_row)

        wb.save(LEADS_FILE)
        return jsonify({"added": len(new_df), "message": f"{len(new_df)} new leads added successfully!"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pause", methods=["POST"])
@login_required
def api_pause():
    global campaign_paused
    campaign_paused = not campaign_paused
    status = "paused" if campaign_paused else "resumed"
    return jsonify({"status": status, "paused": campaign_paused})


@app.route("/api/zapier", methods=["POST"])
def api_zapier():
    """Zapier webhook endpoint — receives new leads from Meta Lead Ads."""
    data = request.json or request.form.to_dict()
    from lead_tracker import load_leads, LEADS_FILE, SHEET_NAME
    from openpyxl import load_workbook

    def fmt_phone(p):
        if not p: return ""
        n = str(p).strip().replace("-","").replace("(","").replace(")","").replace(" ","").replace("+","")
        if len(n) == 10: return f"+1{n}"
        elif len(n) == 11 and n.startswith("1"): return f"+{n}"
        return f"+{n}"

    phone = fmt_phone(data.get("phone") or data.get("cell_phone") or data.get("phone_number",""))
    first_name = str(data.get("first_name") or data.get("name","")).strip()

    if not phone or not first_name:
        return jsonify({"error": "first_name and phone are required"}), 400

    existing_df = load_leads()
    if phone in existing_df["Phone (Formatted)"].astype(str).values:
        return jsonify({"status": "duplicate", "message": "Lead already exists"})

    wb   = load_workbook(LEADS_FILE)
    ws   = wb[SHEET_NAME]
    hdrs = [cell.value for cell in ws[1]]

    row_data = {
        "First Name": first_name,
        "Last Name": str(data.get("last_name","")),
        "Phone (Formatted)": phone,
        "Email": str(data.get("email","")),
        "Buyer/Seller": str(data.get("buyer_seller","Buyer")),
        "Favorite City": str(data.get("city","")),
        "Notes": str(data.get("notes") or data.get("ad_notes","")),
        "SMS Status": "Pending",
        "SMS Sent At": "", "SMS Message Sent": "",
        "Reply Received": "No", "Reply Text": "",
        "Lead Temperature": "", "Follow Up Required": "", "Agent Notes": ""
    }

    ws.append([row_data.get(h, "") for h in hdrs])
    wb.save(LEADS_FILE)
    return jsonify({"status": "success", "message": f"Lead {first_name} added"})


# ─── EXISTING ROUTES ──────────────────────────────────────────────────────────

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

    words         = len(ai_reply.split())
    typing_delay  = random.randint(20, 45) + (words // 5)

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
@login_required
def manual_trigger():
    thread = threading.Thread(target=run_daily_campaign)
    thread.daemon = True
    thread.start()
    return jsonify({"status": "campaign triggered"})


# ─── HTML TEMPLATES ───────────────────────────────────────────────────────────

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Aman's Agent — Login</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { background:#0f172a; display:flex; align-items:center; justify-content:center; height:100vh; font-family:Arial,sans-serif; }
        .card { background:#1e293b; padding:40px; border-radius:12px; width:360px; text-align:center; }
        h2 { color:#fff; margin-bottom:8px; }
        p { color:#94a3b8; margin-bottom:24px; font-size:14px; }
        input { width:100%; padding:12px; border-radius:8px; border:1px solid #334155; background:#0f172a; color:#fff; font-size:15px; margin-bottom:16px; }
        button { width:100%; padding:12px; background:#3b82f6; color:#fff; border:none; border-radius:8px; font-size:15px; cursor:pointer; font-weight:bold; }
        button:hover { background:#2563eb; }
        .error { color:#f87171; font-size:13px; margin-bottom:12px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🏠 Aman's Reactivation Agent</h2>
        <p>Royal LePage — Command Centre</p>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <input type="password" name="password" placeholder="Enter password" autofocus>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Aman's Reactivation Agent</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { background:#0f172a; color:#e2e8f0; font-family:Arial,sans-serif; }
        .header { background:#1e293b; padding:16px 24px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #334155; }
        .header h1 { font-size:18px; color:#fff; }
        .header span { font-size:13px; color:#94a3b8; }
        .header-right { display:flex; gap:10px; align-items:center; }
        .btn { padding:8px 16px; border-radius:8px; border:none; cursor:pointer; font-size:13px; font-weight:bold; }
        .btn-blue { background:#3b82f6; color:#fff; }
        .btn-blue:hover { background:#2563eb; }
        .btn-green { background:#22c55e; color:#fff; }
        .btn-green:hover { background:#16a34a; }
        .btn-red { background:#ef4444; color:#fff; }
        .btn-red:hover { background:#dc2626; }
        .btn-yellow { background:#f59e0b; color:#fff; }
        .btn-yellow:hover { background:#d97706; }
        .btn-gray { background:#475569; color:#fff; }
        .btn-gray:hover { background:#334155; }
        .stats { display:grid; grid-template-columns:repeat(6,1fr); gap:12px; padding:20px 24px; }
        .stat-card { background:#1e293b; border-radius:10px; padding:16px; text-align:center; border:1px solid #334155; }
        .stat-card .num { font-size:28px; font-weight:bold; margin-bottom:4px; }
        .stat-card .label { font-size:12px; color:#94a3b8; }
        .hot-num { color:#f87171; }
        .warm-num { color:#fbbf24; }
        .sent-num { color:#60a5fa; }
        .replied-num { color:#34d399; }
        .main { display:grid; grid-template-columns:1fr 380px; gap:16px; padding:0 24px 24px; }
        .panel { background:#1e293b; border-radius:10px; border:1px solid #334155; }
        .panel-header { padding:14px 16px; border-bottom:1px solid #334155; display:flex; align-items:center; justify-content:space-between; }
        .panel-header h3 { font-size:14px; font-weight:bold; }
        .filters { display:flex; gap:8px; padding:12px 16px; border-bottom:1px solid #334155; flex-wrap:wrap; }
        .filter-btn { padding:5px 12px; border-radius:20px; border:1px solid #334155; background:transparent; color:#94a3b8; cursor:pointer; font-size:12px; }
        .filter-btn.active { background:#3b82f6; color:#fff; border-color:#3b82f6; }
        .search-box { padding:12px 16px; border-bottom:1px solid #334155; }
        .search-box input { width:100%; padding:8px 12px; border-radius:8px; border:1px solid #334155; background:#0f172a; color:#fff; font-size:13px; }
        .leads-table { overflow-y:auto; max-height:500px; }
        table { width:100%; border-collapse:collapse; font-size:13px; }
        th { padding:10px 12px; text-align:left; color:#94a3b8; font-size:11px; text-transform:uppercase; position:sticky; top:0; background:#1e293b; border-bottom:1px solid #334155; }
        td { padding:10px 12px; border-bottom:1px solid #1e293b; cursor:pointer; }
        tr:hover td { background:#263548; }
        tr.selected td { background:#1d3a5e; }
        .badge { padding:3px 8px; border-radius:12px; font-size:11px; font-weight:bold; }
        .badge-hot { background:#fee2e2; color:#dc2626; }
        .badge-warm { background:#fef9c3; color:#b45309; }
        .badge-cold { background:#e0e7ff; color:#4338ca; }
        .badge-pending { background:#f1f5f9; color:#475569; }
        .badge-sent { background:#dbeafe; color:#1d4ed8; }
        .badge-replied { background:#dcfce7; color:#15803d; }
        .badge-optout { background:#fee2e2; color:#9f1239; }
        .conv-panel { display:flex; flex-direction:column; }
        .conv-messages { flex:1; overflow-y:auto; padding:16px; max-height:380px; min-height:200px; }
        .msg { margin-bottom:12px; }
        .msg-out { text-align:right; }
        .msg-bubble { display:inline-block; padding:8px 12px; border-radius:12px; font-size:13px; max-width:85%; line-height:1.4; }
        .msg-out .msg-bubble { background:#3b82f6; color:#fff; border-radius:12px 12px 2px 12px; }
        .msg-in .msg-bubble { background:#334155; color:#e2e8f0; border-radius:12px 12px 12px 2px; }
        .msg-label { font-size:11px; color:#64748b; margin-bottom:3px; }
        .reply-box { padding:12px 16px; border-top:1px solid #334155; }
        .reply-box textarea { width:100%; padding:10px; border-radius:8px; border:1px solid #334155; background:#0f172a; color:#fff; font-size:13px; resize:none; height:70px; margin-bottom:8px; }
        .reply-box button { width:100%; }
        .empty-state { padding:40px; text-align:center; color:#475569; font-size:13px; }
        .upload-area { padding:16px; }
        .upload-area input { display:none; }
        .upload-label { display:block; padding:16px; border:2px dashed #334155; border-radius:8px; text-align:center; cursor:pointer; color:#94a3b8; font-size:13px; }
        .upload-label:hover { border-color:#3b82f6; color:#3b82f6; }
        .toast { position:fixed; bottom:24px; right:24px; background:#22c55e; color:#fff; padding:12px 20px; border-radius:8px; font-size:13px; font-weight:bold; display:none; z-index:999; }
        .toast.error { background:#ef4444; }
        .status-dot { width:8px; height:8px; border-radius:50%; display:inline-block; margin-right:6px; }
        .dot-green { background:#22c55e; }
        .dot-red { background:#ef4444; }
        .dot-yellow { background:#f59e0b; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
    </style>
</head>
<body>

<div class="header">
    <div>
        <h1>🏠 Aman's Reactivation Agent</h1>
        <span id="agent-status"><span class="status-dot dot-yellow"></span>Loading...</span>
    </div>
    <div class="header-right">
        <button class="btn btn-green" onclick="triggerCampaign()">🚀 Launch Campaign</button>
        <button class="btn btn-yellow" id="pause-btn" onclick="togglePause()">⏸ Pause</button>
        <button class="btn btn-gray" onclick="window.location='/{{ secret_path }}/logout'">Logout</button>
    </div>
</div>

<div class="stats">
    <div class="stat-card"><div class="num" id="stat-total">—</div><div class="label">Total Leads</div></div>
    <div class="stat-card"><div class="num sent-num" id="stat-sent">—</div><div class="label">SMS Sent</div></div>
    <div class="stat-card"><div class="num" id="stat-pending">—</div><div class="label">Pending</div></div>
    <div class="stat-card"><div class="num replied-num" id="stat-replied">—</div><div class="label">Replied</div></div>
    <div class="stat-card"><div class="num hot-num" id="stat-hot">—</div><div class="label">🔥 Hot Leads</div></div>
    <div class="stat-card"><div class="num warm-num" id="stat-warm">—</div><div class="label">🌡️ Warm Leads</div></div>
</div>

<div class="main">
    <!-- LEFT: Leads Table -->
    <div class="panel">
        <div class="panel-header">
            <h3>All Leads</h3>
            <span id="leads-count" style="font-size:12px;color:#94a3b8;"></span>
        </div>
        <div class="filters">
            <button class="filter-btn active" onclick="setFilter('all',this)">All</button>
            <button class="filter-btn" onclick="setFilter('hot',this)">🔥 Hot</button>
            <button class="filter-btn" onclick="setFilter('warm',this)">🌡️ Warm</button>
            <button class="filter-btn" onclick="setFilter('replied',this)">💬 Replied</button>
            <button class="filter-btn" onclick="setFilter('pending',this)">⏳ Pending</button>
        </div>
        <div class="search-box">
            <input type="text" id="search-input" placeholder="🔍 Search by name or phone..." oninput="searchLeads()">
        </div>
        <div class="leads-table">
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Phone</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Temperature</th>
                    </tr>
                </thead>
                <tbody id="leads-tbody">
                    <tr><td colspan="5" class="empty-state">Loading leads...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- RIGHT: Conversation + Upload -->
    <div style="display:flex;flex-direction:column;gap:16px;">

        <!-- Conversation Panel -->
        <div class="panel conv-panel" style="flex:1;">
            <div class="panel-header">
                <h3 id="conv-title">Select a lead to view conversation</h3>
            </div>
            <div class="conv-messages" id="conv-messages">
                <div class="empty-state">Click any lead on the left to view their conversation and reply manually.</div>
            </div>
            <div class="reply-box" id="reply-box" style="display:none;">
                <textarea id="reply-text" placeholder="Type your message as Sarah..."></textarea>
                <button class="btn btn-blue" onclick="sendManualReply()" style="width:100%;">Send as Sarah</button>
            </div>
        </div>

        <!-- Upload New Leads -->
        <div class="panel">
            <div class="panel-header"><h3>📁 Upload New Leads</h3></div>
            <div class="upload-area">
                <label class="upload-label" for="file-upload">
                    📂 Click to upload Excel/CSV leads file<br>
                    <small style="color:#64748b;">Duplicates removed automatically</small>
                </label>
                <input type="file" id="file-upload" accept=".xlsx,.csv" onchange="uploadLeads(this)">
            </div>
        </div>

    </div>
</div>

<div class="toast" id="toast"></div>

<script>
let currentFilter = 'all';
let currentPhone = null;
let searchTimer = null;

async function loadStats() {
    const r = await fetch('/api/stats');
    const d = await r.json();
    document.getElementById('stat-total').textContent   = d.total || 0;
    document.getElementById('stat-sent').textContent    = d.sent || 0;
    document.getElementById('stat-pending').textContent = d.pending || 0;
    document.getElementById('stat-replied').textContent = d.replied || 0;
    document.getElementById('stat-hot').textContent     = d.hot || 0;
    document.getElementById('stat-warm').textContent    = d.warm || 0;

    const statusEl = document.getElementById('agent-status');
    const pauseBtn = document.getElementById('pause-btn');
    if (d.paused) {
        statusEl.innerHTML = '<span class="status-dot dot-red"></span>Campaign Paused';
        pauseBtn.textContent = '▶ Resume';
        pauseBtn.className = 'btn btn-green';
    } else {
        statusEl.innerHTML = '<span class="status-dot dot-green"></span>Agent Running';
        pauseBtn.textContent = '⏸ Pause';
        pauseBtn.className = 'btn btn-yellow';
    }
}

async function loadLeads() {
    const search = document.getElementById('search-input').value;
    const url    = `/api/leads?filter=${currentFilter}&search=${encodeURIComponent(search)}`;
    const r      = await fetch(url);
    const d      = await r.json();
    document.getElementById('leads-count').textContent = `${d.total} leads`;

    const tbody = document.getElementById('leads-tbody');
    if (!d.leads || d.leads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No leads found</td></tr>';
        return;
    }

    tbody.innerHTML = d.leads.map(l => {
        const name   = `${l['First Name']} ${l['Last Name']}`.trim();
        const phone  = l['Phone (Formatted)'] || '';
        const type   = l['Buyer/Seller'] || '—';
        const status = l['SMS Status'] || 'Pending';
        const temp   = l['Lead Temperature'] || '';

        const statusBadge = {
            'Sent': '<span class="badge badge-sent">Sent</span>',
            'Pending': '<span class="badge badge-pending">Pending</span>',
            'Opted Out': '<span class="badge badge-optout">Opted Out</span>',
        }[status] || `<span class="badge badge-pending">${status}</span>`;

        const tempBadge = {
            'Hot':  '<span class="badge badge-hot">🔥 Hot</span>',
            'Warm': '<span class="badge badge-warm">🌡️ Warm</span>',
            'Cold': '<span class="badge badge-cold">❄️ Cold</span>',
        }[temp] || '';

        const sel = currentPhone === phone ? 'selected' : '';
        return `<tr class="${sel}" onclick="selectLead('${phone}','${name}')">
            <td>${name}</td>
            <td style="color:#94a3b8;font-size:12px;">${phone}</td>
            <td style="font-size:12px;">${type}</td>
            <td>${statusBadge}</td>
            <td>${tempBadge}</td>
        </tr>`;
    }).join('');
}

async function selectLead(phone, name) {
    currentPhone = phone;
    document.getElementById('conv-title').textContent = name;
    document.getElementById('reply-box').style.display = 'block';

    const r = await fetch(`/api/conversation/${encodeURIComponent(phone)}`);
    const d = await r.json();

    const messagesEl = document.getElementById('conv-messages');
    let html = '';

    if (d.initial_message) {
        html += `<div class="msg msg-out"><div class="msg-label">Sarah (Agent)</div><div class="msg-bubble">${d.initial_message}</div></div>`;
    }
    if (d.reply_text) {
        html += `<div class="msg msg-in"><div class="msg-label">Lead</div><div class="msg-bubble">${d.reply_text}</div></div>`;
    }
    if (d.history && d.history.length > 0) {
        d.history.forEach(m => {
            if (m.role === 'assistant') {
                html += `<div class="msg msg-out"><div class="msg-label">Sarah (Agent)</div><div class="msg-bubble">${m.content}</div></div>`;
            } else {
                html += `<div class="msg msg-in"><div class="msg-label">Lead</div><div class="msg-bubble">${m.content}</div></div>`;
            }
        });
    }

    messagesEl.innerHTML = html || '<div class="empty-state">No messages yet</div>';
    messagesEl.scrollTop = messagesEl.scrollHeight;
    loadLeads();
}

async function sendManualReply() {
    const msg = document.getElementById('reply-text').value.trim();
    if (!msg || !currentPhone) return;
    const r = await fetch('/api/reply', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({phone: currentPhone, message: msg})
    });
    const d = await r.json();
    if (d.success) {
        document.getElementById('reply-text').value = '';
        showToast('Message sent!');
        selectLead(currentPhone, document.getElementById('conv-title').textContent);
    } else {
        showToast('Failed to send', true);
    }
}

async function triggerCampaign() {
    if (!confirm('Launch campaign now? This will start sending SMS to pending leads.')) return;
    const r = await fetch('/trigger');
    const d = await r.json();
    showToast('🚀 Campaign launched! Messages sending now...');
    setTimeout(loadStats, 3000);
}

async function togglePause() {
    const r = await fetch('/api/pause', {method:'POST'});
    const d = await r.json();
    showToast(d.status === 'paused' ? '⏸ Campaign paused' : '▶ Campaign resumed');
    loadStats();
}

function setFilter(filter, el) {
    currentFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    el.classList.add('active');
    loadLeads();
}

function searchLeads() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadLeads, 300);
}

async function uploadLeads(input) {
    const file = input.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    showToast('Uploading leads...');
    const r = await fetch('/api/upload', {method:'POST', body: formData});
    const d = await r.json();
    if (d.error) {
        showToast(d.error, true);
    } else {
        showToast(`✅ ${d.message}`);
        loadStats();
        loadLeads();
    }
    input.value = '';
}

function showToast(msg, isError=false) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast' + (isError ? ' error' : '');
    t.style.display = 'block';
    setTimeout(() => t.style.display = 'none', 4000);
}

// Init
loadStats();
loadLeads();
setInterval(() => { loadStats(); loadLeads(); }, 30000);
</script>
</body>
</html>
"""

# Start background scheduler thread
scheduler_thread = threading.Thread(target=scheduler_loop)
scheduler_thread.daemon = True
scheduler_thread.start()
print("[AGENT] Background scheduler started")
