import os
import sqlite3
import logging
import requests
from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv

# Environment variables load karein
load_dotenv()

app = Flask(__name__)

# Logging setup (Errors check karne ke liye)
logging.basicConfig(level=logging.INFO)

# OpenAI Client Setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Database Setup (User memory ke liye)
def init_db():
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (phone TEXT, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

init_db()

# WhatsApp ko reply bhejne ka function
def send_whatsapp_message(to_phone, message_text):
    url = f"https://graph.facebook.com/v18.0/{os.getenv('PHONE_NUMBER_ID')}/messages"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN')}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message_text}
    }
    response = requests.post(url, headers=headers, json=data)
    return response

# AI se jawab mangne ka function
def get_ai_response(phone, user_input):
    # Purani history nikalna
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE phone = ? LIMIT 5", (phone,))
    rows = c.fetchall()
    
    messages = [{"role": "system", "content": "You are Taimur Trading Bot. Give professional trading advice."}]
    for role, content in rows:
        messages.append({"role": role, "content": content})
    
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=150
        )
        answer = response.choices[0].message.content
        
        # History save karna
        c.execute("INSERT INTO messages VALUES (?, ?, ?)", (phone, "user", user_input))
        c.execute("INSERT INTO messages VALUES (?, ?, ?)", (phone, "assistant", answer))
        conn.commit()
        conn.close()
        return answer
    except Exception as e:
        return "Sorry, AI system mein masla hai. Thori dair baad koshish karein."

# Webhook Verification (Meta Dashboard ke liye)
@app.route('/webhook', methods=['GET'])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == os.getenv("VERIFY_TOKEN"):
        return challenge
    return "Token mismatch", 403

# Main Webhook (Messages receive karne ke liye)
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    try:
        if "messages" in data["entry"][0]["changes"][0]["value"]:
            message = data["entry"][0]["changes"][0]["value"]["messages"][0]
            phone = message["from"]
            text = message["text"]["body"]
            
            # AI Response hasil karein
            ai_reply = get_ai_response(phone, text)
            
            # WhatsApp par reply bhejein
            send_whatsapp_message(phone, ai_reply)
            
        return "SUCCESS", 200
    except Exception as e:
        return "ERROR", 500

if __name__ == "__main__":
    app.run(port=8000)
