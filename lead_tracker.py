"""
lead_tracker.py — PostgreSQL-backed lead management
Replaces the old Excel-based implementation.
Railway injects DATABASE_URL automatically when you add a PostgreSQL service.
"""
import os
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://")


def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    """Create tables on first run — safe to call every startup."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id                  SERIAL PRIMARY KEY,
                    first_name          TEXT DEFAULT '',
                    last_name           TEXT DEFAULT '',
                    phone               TEXT UNIQUE NOT NULL,
                    email               TEXT DEFAULT '',
                    buyer_seller        TEXT DEFAULT 'Buyer',
                    phase               TEXT DEFAULT 'Phase 1',
                    city                TEXT DEFAULT '',
                    pipeline_stage      TEXT DEFAULT '',
                    source              TEXT DEFAULT '',
                    notes               TEXT DEFAULT '',
                    sms_status          TEXT DEFAULT 'Pending',
                    sms_sent_at         TEXT DEFAULT '',
                    sms_message_sent    TEXT DEFAULT '',
                    reply_received      TEXT DEFAULT 'No',
                    reply_text          TEXT DEFAULT '',
                    lead_temperature    TEXT DEFAULT '',
                    follow_up_required  TEXT DEFAULT '',
                    agent_notes         TEXT DEFAULT '',
                    created_at          TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id         SERIAL PRIMARY KEY,
                    phone      TEXT NOT NULL,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_conv_phone ON conversations(phone);
            """)
            conn.commit()
    print("[DB] Tables ready")


def load_leads() -> pd.DataFrame:
    """Load all leads as a DataFrame with familiar column names."""
    cols = [
        'first_name', 'last_name', 'phone', 'email', 'buyer_seller', 'phase',
        'city', 'pipeline_stage', 'source', 'notes', 'sms_status', 'sms_sent_at',
        'sms_message_sent', 'reply_received', 'reply_text', 'lead_temperature',
        'follow_up_required', 'agent_notes'
    ]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(cols)} FROM leads ORDER BY id")
            rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=cols)
    return df.rename(columns={
        'first_name': 'First Name',        'last_name': 'Last Name',
        'phone': 'Phone (Formatted)',       'email': 'Email',
        'buyer_seller': 'Buyer/Seller',     'phase': 'Phase',
        'city': 'Favorite City',            'pipeline_stage': 'Pipeline Stage',
        'source': 'Source',                 'notes': 'Notes',
        'sms_status': 'SMS Status',         'sms_sent_at': 'SMS Sent At',
        'sms_message_sent': 'SMS Message Sent',
        'reply_received': 'Reply Received', 'reply_text': 'Reply Text',
        'lead_temperature': 'Lead Temperature',
        'follow_up_required': 'Follow Up Required',
        'agent_notes': 'Agent Notes'
    })


def get_pending_leads(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["SMS Status"] == "Pending"].copy()


def get_followup_leads(df: pd.DataFrame) -> pd.DataFrame:
    from config import FOLLOWUP_DAYS
    now  = datetime.now()
    mask = (
        (df["SMS Status"] == "Sent") &
        (df["Reply Received"] == "No") &
        (df["SMS Sent At"] != "") &
        (df["SMS Sent At"].notna())
    )
    candidates = df[mask].copy()
    if candidates.empty:
        return candidates
    candidates["SMS Sent At"] = pd.to_datetime(candidates["SMS Sent At"], errors="coerce")
    return candidates[(now - candidates["SMS Sent At"]).dt.days >= FOLLOWUP_DAYS]


def add_lead(data: dict) -> bool:
    """Insert a lead. Returns True if added, False if duplicate phone."""
    phone = str(data.get('phone', '')).strip()
    if not phone:
        return False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO leads
                        (first_name, last_name, phone, email, buyer_seller,
                         phase, city, notes, sms_status, reply_received)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Pending', 'No')
                    ON CONFLICT (phone) DO NOTHING
                    RETURNING id
                """, (
                    data.get('first_name', ''), data.get('last_name', ''),
                    phone,                      data.get('email', ''),
                    data.get('buyer_seller', 'Buyer'),
                    data.get('phase', 'Phase 1'),
                    data.get('city', ''),        data.get('notes', '')
                ))
                result = cur.fetchone()
                conn.commit()
                return result is not None
    except Exception as e:
        print(f"[DB] add_lead error: {e}")
        return False


def update_lead_sent(phone: str, message: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE leads SET sms_status='Sent',
                    sms_sent_at=%s, sms_message_sent=%s
                WHERE phone=%s
            """, (datetime.now().strftime("%Y-%m-%d %H:%M"), message, phone))
            conn.commit()


def update_lead_reply(phone: str, reply_text: str, temperature: str = ""):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE leads SET reply_received='Yes',
                    reply_text=%s, lead_temperature=%s
                WHERE phone=%s
            """, (reply_text, temperature, phone))
            conn.commit()


def update_lead_optout(phone: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE leads SET sms_status='Opted Out', follow_up_required='No'
                WHERE phone=%s
            """, (phone,))
            conn.commit()


def get_conversation(phone: str) -> list:
    """Return full conversation history for a phone number."""
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT role, content FROM conversations
                    WHERE phone=%s ORDER BY created_at
                """, (phone,))
                return [{"role": r["role"], "content": r["content"]}
                        for r in cur.fetchall()]
    except Exception:
        return []


def save_message(phone: str, role: str, content: str):
    """Persist a single message to the conversations table."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO conversations (phone, role, content)
                    VALUES (%s, %s, %s)
                """, (phone, role, content))
                conn.commit()
    except Exception as e:
        print(f"[DB] save_message error: {e}")


def migrate_from_excel():
    """One-time migration: import Excel leads if the DB is empty."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM leads")
                count = cur.fetchone()[0]
        if count > 0:
            print(f"[MIGRATE] DB already has {count} leads — skipping Excel import")
            return
    except Exception as e:
        print(f"[MIGRATE] DB check failed: {e}")
        return

    excel_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "leads", "Aman_Pilot_Leads_179.xlsx"
    )
    if not os.path.exists(excel_path):
        print("[MIGRATE] No Excel file found — starting fresh DB")
        return

    print("[MIGRATE] Importing leads from Excel into PostgreSQL...")
    try:
        df = pd.read_excel(excel_path, sheet_name="Pilot Leads (179)")
        imported = 0
        for _, row in df.iterrows():
            phone = str(row.get("Phone (Formatted)", "") or "").strip()
            if not phone or phone.lower() == "nan":
                continue
            if add_lead({
                'first_name':  str(row.get("First Name",    "") or ""),
                'last_name':   str(row.get("Last Name",     "") or ""),
                'phone':       phone,
                'email':       str(row.get("Email",         "") or ""),
                'buyer_seller':str(row.get("Buyer/Seller",  "") or "Buyer"),
                'phase':       str(row.get("Phase",         "") or "Phase 1"),
                'city':        str(row.get("Favorite City", "") or ""),
                'notes':       str(row.get("Notes",         "") or ""),
            }):
                imported += 1
        print(f"[MIGRATE] Done — {imported} leads imported from Excel")
    except Exception as e:
        print(f"[MIGRATE] Failed: {e}")
