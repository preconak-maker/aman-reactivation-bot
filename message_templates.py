from config import AGENT_NAME, TEAM_NAME, BROKERAGE

OPT_OUT = "Reply STOP to opt out."

def get_initial_message(first_name: str, buyer_seller: str, favorite_city: str = None) -> str:
    """Generate personalized initial reactivation SMS."""
    city_line = f" in {favorite_city}" if favorite_city and str(favorite_city).strip() not in ["", "nan", "None"] else ""

    if buyer_seller in ["Buyer"]:
        return (
            f"Hi {first_name}! This is {AGENT_NAME} from {TEAM_NAME} at {BROKERAGE}. "
            f"We connected a while back — wanted to reach out personally. "
            f"Are you still thinking about buying a home{city_line}, or has your situation changed? "
            f"No pressure at all, just checking in! {OPT_OUT}"
        )
    elif buyer_seller in ["Both"]:
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
            f"Are you still thinking about real estate, or has your situation changed? "
            f"No pressure — just here to help! {OPT_OUT}"
        )

def get_followup_message(first_name: str) -> str:
    """3-day follow-up if no reply."""
    return (
        f"Hi {first_name}, just circling back! {AGENT_NAME} from {TEAM_NAME}. "
        f"Did you get a chance to see my last message? "
        f"Happy to share what's happening in the market — completely free, no commitment. "
        f"Just reply YES if you'd like to chat! {OPT_OUT}"
    )

# Objection handling context for Claude AI
SYSTEM_PROMPT = f"""You are {AGENT_NAME}, a friendly real estate assistant from {TEAM_NAME} at {BROKERAGE} in Canada.
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
- "Not ready yet" → Ask when would be a good time to follow up, offer market newsletter
- "I'll get back to you" → Set a tentative time, easy to reschedule
- "Need to check with spouse" → Set tentative time, can always change it

Goal: Get them to agree to a 15-20 minute call or meeting with Aman.
When they agree, say: "Perfect! Aman will reach out directly to confirm a time. What's the best time — days or evenings?"

Always end with either:
1. A soft question to keep them talking
2. A meeting ask
3. Opt-out confirmation if they said STOP
"""
