import os
from message_templates import SYSTEM_PROMPT


def get_twilio_client():
    from twilio.rest import Client
    return Client(
        os.environ.get("TWILIO_ACCOUNT_SID"),
        os.environ.get("TWILIO_AUTH_TOKEN")
    )


def get_claude_client():
    import anthropic
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def send_sms(to_number: str, message: str) -> bool:
    try:
        client = get_twilio_client()
        msg = client.messages.create(
            body=message,
            from_=os.environ.get("TWILIO_PHONE"),
            to=to_number
        )
        print(f"[SENT] {to_number} | SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send to {to_number}: {e}")
        return False


def generate_ai_reply(conversation_history: list, incoming_message: str) -> str:
    client = get_claude_client()
    conversation_history.append({
        "role": "user",
        "content": incoming_message
    })
    response = client.messages.create(
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
    client = get_claude_client()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system="Classify this real estate lead reply as exactly one word: Hot, Warm, or Cold.",
        messages=[{"role": "user", "content": reply_text}]
    )
    temp = response.content[0].text.strip()
    if temp not in ["Hot", "Warm", "Cold"]:
        return "Warm"
    return temp
