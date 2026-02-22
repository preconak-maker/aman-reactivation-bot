from twilio.rest import Client
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE
import anthropic
from config import ANTHROPIC_API_KEY
from message_templates import SYSTEM_PROMPT

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
claude_client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def send_sms(to_number: str, message: str) -> bool:
    """Send SMS via Twilio. Returns True if successful."""
    try:
        msg = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=to_number
        )
        print(f"[SENT] {to_number} | SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send to {to_number}: {e}")
        return False


def generate_ai_reply(conversation_history: list, incoming_message: str) -> str:
    """Use Claude to generate a smart reply based on conversation history."""
    conversation_history.append({
        "role": "user",
        "content": incoming_message
    })

    response = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=conversation_history
    )

    reply = response.content[0].text.strip()

    conversation_history.append({
        "role": "assistant",
        "content": reply
    })

    return reply


def classify_lead_temperature(reply_text: str) -> str:
    """Classify reply as Hot / Warm / Cold using Claude."""
    response = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system="Classify this real estate lead reply as exactly one word: Hot, Warm, or Cold.",
        messages=[{"role": "user", "content": reply_text}]
    )
    temp = response.content[0].text.strip()
    if temp not in ["Hot", "Warm", "Cold"]:
        return "Warm"
    return temp
