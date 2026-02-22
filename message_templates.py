from config import AGENT_NAME, TEAM_NAME, BROKERAGE

OPT_OUT = "Reply STOP to opt out."

# ── PHASE 1 — Last 2 years (Direct, confident) ────────────────────────────────

def get_initial_message(first_name: str, buyer_seller: str, favorite_city: str = None, phase: str = "Phase 1") -> str:
    city_line = f" in {favorite_city}" if favorite_city and str(favorite_city).strip() not in ["", "nan", "None"] else ""
    if phase == "Phase 2":
        return get_phase2_message(first_name, buyer_seller, city_line)
    elif phase == "Phase 3":
        return get_phase3_message(first_name)
    else:
        return get_phase1_message(first_name, buyer_seller, city_line)


def get_phase1_message(first_name: str, buyer_seller: str, city_line: str) -> str:
    if buyer_seller == "Buyer":
        return (
            f"Hi {first_name}! This is {AGENT_NAME} from {TEAM_NAME} at {BROKERAGE}. "
            f"We connected a while back — wanted to reach out personally. "
            f"Are you still thinking about buying a home{city_line}, or has your situation changed? "
            f"No pressure at all, just checking in! {OPT_OUT}"
        )
    elif buyer_seller in ["Both", "Seller"]:
        return (
            f"Hi {first_name}, {AGENT_NAME} here from {TEAM_NAME} at {BROKERAGE}. "
            f"It's been a while since we connected — are you still thinking about making a move{city_line}? "
            f"The market right now has some interesting opportunities. "
            f"Happy to share what we're seeing, no obligation at all. {OPT_OUT}"
        )
    else:
        return (
            f"Hi {first_name}! This is {AGENT_NAME} from {TEAM_NAME} at {BROKERAGE}. "
            f"We connected a while back and just wanted to check in. "
            f"Are you still thinking about real estate{city_line}? "
            f"No pressure — just here to help! {OPT_OUT}"
        )


# ── PHASE 2 — 2 to 5 years (Softer, warmer) ──────────────────────────────────

def get_phase2_message(first_name: str, buyer_seller: str, city_line: str) -> str:
    if buyer_seller == "Buyer":
        return (
            f"Hi {first_name}! Hope you're doing well. "
            f"This is {AGENT_NAME} from {TEAM_NAME} at {BROKERAGE} — we crossed paths a few years back. "
            f"I know life gets busy but I wanted to reach out — "
            f"has buying a home{city_line} ever come back on your radar? "
            f"Happy to chat anytime, completely free. {OPT_OUT}"
        )
    elif buyer_seller in ["Both", "Seller"]:
        return (
            f"Hi {first_name}, hope things are going well! "
            f"{AGENT_NAME} here from {TEAM_NAME} at {BROKERAGE}. "
            f"We connected a few years ago and I just wanted to check in — "
            f"has making a move{city_line} ever come back on your mind? "
            f"The market has changed quite a bit since we last spoke. "
            f"No pressure at all — just here if you ever want to talk! {OPT_OUT}"
        )
    else:
        return (
            f"Hi {first_name}! Hope you're well. "
            f"This is {AGENT_NAME} from {TEAM_NAME} at {BROKERAGE} — "
            f"we crossed paths a few years back around real estate. "
            f"Just wanted to check in and see how things are going. "
            f"Still thinking about buying or selling? Happy to help anytime! {OPT_OUT}"
        )


# ── PHASE 3 — 5+ years (Re-consent, very soft) ───────────────────────────────

def get_phase3_message(first_name: str) -> str:
    return (
        f"Hi {first_name}! This is {AGENT_NAME} from {TEAM_NAME} at {BROKERAGE}. "
        f"We're updating our records and wanted to reconnect with some of our older contacts. "
        f"Are you still interested in real estate at all, or would you prefer we don't reach out? "
        f"Either answer is totally fine — just reply YES to stay in touch or STOP to unsubscribe. {OPT_OUT}"
    )


# ── FOLLOW UP MESSAGES ────────────────────────────────────────────────────────

def get_followup_message(first_name: str, phase: str = "Phase 1") -> str:
    if phase == "Phase 2":
        return (
            f"Hi {first_name}, just following up on my message from a few days ago! "
            f"{AGENT_NAME} from {TEAM_NAME}. "
            f"No pressure at all — just wanted to make sure you got it. "
            f"Would love to reconnect whenever you're ready. Reply STOP to opt out."
        )
    elif phase == "Phase 3":
        return (
            f"Hi {first_name}, just circling back — {AGENT_NAME} from {TEAM_NAME}. "
            f"Did you get a chance to see my last message? "
            f"Just reply YES to stay in touch or STOP to unsubscribe. "
            f"Either way is perfectly fine!"
        )
    else:
        return (
            f"Hi {first_name}, just circling back! {AGENT_NAME} from {TEAM_NAME}. "
            f"Did you get a chance to see my last message? "
            f"Happy to share what's happening in the market — completely free, no commitment. "
            f"Just say YES if you'd like to chat! {OPT_OUT}"
        )


# ── BROADCAST MESSAGE ─────────────────────────────────────────────────────────

def get_broadcast_message(first_name: str, custom_message: str, phase: str = "Phase 1") -> str:
    greeting = f"Hi {first_name}! " if phase == "Phase 1" else f"Hi {first_name}, hope you're well! "
    return f"{greeting}{custom_message} {OPT_OUT}"


# ── AI SYSTEM PROMPTS BY PHASE ────────────────────────────────────────────────

def get_system_prompt(phase: str = "Phase 1") -> str:
    base = f"""You are {AGENT_NAME}, a friendly real estate assistant from {TEAM_NAME} at {BROKERAGE} in Canada.
Your goal is to qualify leads and book a free 15-20 minute meeting or call with Aman Khattra.

Key rules:
- Always be warm, low-pressure, and helpful
- Never pushy or salesy
- Always offer the meeting as FREE with NO obligation, nothing to sign
- Keep SMS replies SHORT (under 160 characters when possible)
- Always end with a question to keep the conversation going
- If they say STOP or unsubscribe, immediately confirm opt-out only

Objection handling:
- "I have another agent" → Offer to send exclusive listings (bank sales, distress sales) as a free supplement
- "Just send me listings" → Explain 70-criteria form saves them hours, ask for 15 min meeting
- "Too busy" → Position the 15-min meeting as a time-SAVER
- "Not ready yet" → Ask when would be a good time to follow up
- "I'll get back to you" → Set a tentative time, easy to reschedule
- "Need to check with spouse" → Set tentative time, can always change it

When they agree to meet, say: "Perfect! Aman will reach out directly to confirm a time. What's best — days or evenings?"
"""

    if phase == "Phase 2":
        return base + """
IMPORTANT — This is a Phase 2 lead (2-5 years old):
- Be extra warm and patient — they haven't heard from us in a while
- Never assume they're still looking — ask gently
- If they're not ready, ask if it's okay to follow up in a few months
- Tone: like reconnecting with an old acquaintance, not a sales call
"""
    elif phase == "Phase 3":
        return base + """
IMPORTANT — This is a Phase 3 lead (5+ years old):
- Primary goal is RE-CONSENT — get them to say YES to staying in touch
- Do NOT push for a meeting on first reply — just get permission first
- Be very soft, respectful, and understanding
- If they say YES — then gently introduce the idea of a free chat
- Tone: like reconnecting with someone you haven't spoken to in years
"""
    else:
        return base + """
IMPORTANT — This is a Phase 1 lead (last 2 years):
- They're recent — be confident and direct
- Goal is to book the 15-20 minute free meeting quickly
- Tone: friendly, professional, like a knowledgeable friend in real estate
"""

SYSTEM_PROMPT = get_system_prompt("Phase 1")
