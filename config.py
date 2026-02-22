import os

# Twilio
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE       = os.environ.get("TWILIO_PHONE", "")

# Anthropic
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")

# Agent settings
AGENT_NAME         = "Sarah"
TEAM_NAME          = "Aman's team"
BROKERAGE          = "Royal LePage"
DAILY_SEND_LIMIT   = 50          # max SMS per day
SEND_HOUR_START    = 9           # 9am local
SEND_HOUR_END      = 20          # 8pm local
FOLLOWUP_DAYS      = 3           # days before follow-up if no reply
LEADS_FILE         = "leads/Aman_Pilot_Leads_179.xlsx"
SHEET_NAME         = "Pilot Leads (179)"
