import os
import json
import sqlite3
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Department of Skill Education WhatsApp Survey Agent")

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "replace-this-verification-token")
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v23.0")
DB_PATH = os.getenv("DATABASE_PATH", "survey.db")

QUESTIONS = {
    "en": [
        ("name", "What is your name?", "text"),
        ("gender", "What is your gender?", "choice", ["Female", "Male", "Other", "Prefer not to say"]),
        ("status", "What best describes your current status?", "choice",
         ["Salaried employment", "Self-employed / own business", "Currently studying / training", "Not currently working", "Other"]),
        ("job_alerts", "Would you like to receive job postings from various companies on WhatsApp?", "choice", ["Yes", "No"]),
        ("trade", "What is your trade or skill area? (e.g. Electrician, Fitter, IT)", "text"),
    ],
    "hi": [
        ("name", "आपका नाम क्या है?", "text"),
        ("gender", "आपका लिंग क्या है?", "choice", ["महिला", "पुरुष", "अन्य", "बताना नहीं चाहते"]),
        ("status", "आपकी वर्तमान स्थिति क्या है?", "choice",
         ["वेतनभोगी नौकरी", "स्वरोज़गार / अपना व्यवसाय", "अभी पढ़ाई / प्रशिक्षण कर रहे हैं", "वर्तमान में काम नहीं कर रहे", "अन्य"]),
        ("job_alerts", "क्या आप WhatsApp पर विभिन्न कंपनियों की नौकरी संबंधी जानकारी पाना चाहेंगे?", "choice", ["हाँ", "नहीं"]),
        ("trade", "आपका ट्रेड या कौशल क्षेत्र क्या है? (जैसे इलेक्ट्रीशियन, फिटर, आईटी)", "text"),
    ],
}

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS responses (
      phone TEXT PRIMARY KEY, language TEXT, name TEXT, gender TEXT, employment_status TEXT,
      job_alerts TEXT, trade TEXT, current_step INTEGER DEFAULT 0, completed INTEGER DEFAULT 0,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    con.commit()
    return con

def send_text(to, body):
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        print(f"[DEMO outbound to {to}] {body}")
        return
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PHONE_NUMBER_ID}/messages"
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}}
    response = requests.post(url, json=payload, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}, timeout=20)
    if not response.ok:
        print("WhatsApp send error:", response.text)
        response.raise_for_status()

def get_text(message):
    if message.get("type") == "text":
        return message.get("text", {}).get("body", "").strip()
    if message.get("type") == "button":
        return message.get("button", {}).get("text", "").strip()
    if message.get("type") == "interactive":
        interactive = message.get("interactive", {})
        return (interactive.get("button_reply", {}).get("title") or
                interactive.get("list_reply", {}).get("title") or "").strip()
    return ""

def start_survey(phone, language):
    con = db()
    con.execute("""INSERT INTO responses(phone,language,current_step,completed,updated_at)
      VALUES(?,?,0,0,CURRENT_TIMESTAMP)
      ON CONFLICT(phone) DO UPDATE SET language=excluded.language,current_step=0,completed=0,
      name=NULL,gender=NULL,employment_status=NULL,job_alerts=NULL,trade=NULL,updated_at=CURRENT_TIMESTAMP""",
      (phone, language))
    con.commit()
    con.close()
    welcome = ("Thanks for taking the Department of Skill Education survey." if language == "en"
               else "Department of Skill Education के सर्वेक्षण में भाग लेने के लिए धन्यवाद।")
    send_text(phone, welcome + "\n\n" + QUESTIONS[language][0][1])

def handle_incoming(phone, text):
    normalized = text.lower().strip()
    con = db()
    row = con.execute("SELECT * FROM responses WHERE phone=?", (phone,)).fetchone()

    if normalized in ("start", "survey", "शुरू", "सर्वेक्षण"):
        send_text(phone, "Please choose your language / कृपया भाषा चुनें:\nReply 1 for English\nहिंदी के लिए 2 लिखें")
        con.close()
        return

    if normalized in ("1", "english", "en"):
        con.close()
        start_survey(phone, "en")
        return
    if normalized in ("2", "hindi", "हिंदी", "hi"):
        con.close()
        start_survey(phone, "hi")
        return

    if not row:
        send_text(phone, "Welcome! Reply START to begin the survey.\nनमस्ते! सर्वेक्षण शुरू करने के लिए START लिखें।")
        con.close()
        return

    if row["completed"]:
        send_text(phone, "Your survey is already complete. Thank you! / आपका सर्वेक्षण पूरा हो चुका है। धन्यवाद!")
        con.close()
        return

    lang = row["language"] or "en"
    step = int(row["current_step"])
    question = QUESTIONS[lang][step]
    key = question[0]
    if not text:
        send_text(phone, question[1])
        con.close()
        return

    # Store responses. Job-alert consent is recorded explicitly; do not message opted-out users.
    column = {"name": "name", "gender": "gender", "status": "employment_status",
              "job_alerts": "job_alerts", "trade": "trade"}[key]
    con.execute(f"UPDATE responses SET {column}=?, updated_at=CURRENT_TIMESTAMP WHERE phone=?", (text, phone))
    step += 1
    if step >= len(QUESTIONS[lang]):
        con.execute("UPDATE responses SET current_step=?,completed=1,updated_at=CURRENT_TIMESTAMP WHERE phone=?", (step, phone))
        con.commit()
        con.close()
        send_text(phone, "Thank you! Your response has been recorded.\nधन्यवाद! आपका उत्तर दर्ज कर लिया गया है।")
        return
    con.execute("UPDATE responses SET current_step=?,updated_at=CURRENT_TIMESTAMP WHERE phone=?", (step, phone))
    con.commit()
    con.close()
    next_question = QUESTIONS[lang][step]
    prompt = next_question[1]
    if next_question[2] == "choice":
        prompt += "\n\n" + "\n".join(f"{i+1}. {option}" for i, option in enumerate(next_question[3]))
    send_text(phone, prompt)

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")

@app.post("/webhook")
async def receive_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception as exc:
        print("Invalid webhook JSON:", repr(exc))
        raise HTTPException(status_code=400, detail="Invalid JSON")

    print("Webhook received:", json.dumps(payload, ensure_ascii=False))

    try:
        entries = payload.get("entry", [])

        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})

                for message in value.get("messages", []):
                    phone = message.get("from")
                    text = get_text(message)

                    print("Incoming WhatsApp message:", phone, repr(text))

                    if phone:
                        handle_incoming(phone, text)

    except Exception as exc:
        print("Webhook processing issue:", repr(exc))

    return {"status": "ok"}
                    if phone:
                        handle_incoming(phone, text)
    except Exception as exc:
        print("Webhook processing issue:", repr(exc))
        # Acknowledge quickly; inspect server logs to diagnose setup errors.
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok", "service": "Department of Skill Education survey agent"}

@app.get("/responses")
def responses():
    con = db()
    rows = con.execute("SELECT phone,language,name,gender,employment_status,job_alerts,trade,completed,updated_at FROM responses ORDER BY updated_at DESC").fetchall()
    con.close()
    return [dict(row) for row in rows]
