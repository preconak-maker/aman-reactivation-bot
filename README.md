# Aman's Team — Reactivation SMS Agent

## What This Does
- Sends personalized reactivation SMS to 179 pilot leads via Twilio
- Uses Claude AI to handle replies automatically (objection handling, meeting booking)
- Updates your Excel sheet in real time with replies and lead temperature
- Runs daily at 10am Eastern, 50 messages per day

## Files
- `app.py` — main agent (Flask app + scheduler)
- `config.py` — all settings
- `message_templates.py` — SMS scripts + AI system prompt
- `lead_tracker.py` — reads/writes Excel sheet
- `sms_sender.py` — Twilio + Claude API calls
- `leads/` — put your Excel file here

## Environment Variables (set in Railway)
```
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE=+16471234567
ANTHROPIC_API_KEY=your_key
```

## Twilio Webhook Setup
After deploying to Railway, set your Twilio webhook to:
```
https://your-app.railway.app/webhook/sms
```

## Manual Trigger
Visit `https://your-app.railway.app/trigger` to run campaign immediately.
