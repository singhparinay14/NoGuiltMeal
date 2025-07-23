import gspread
from oauth2client.service_account import ServiceAccountCredentials
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import sqlite3
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---

load_dotenv()

SPREADSHEET_ID = "1UWR5F3c20ZSc7kpf9eKz8OpC5bLFdoHGPwF7F0Apsm0"
GOOGLE_KEY_FILE = os.getenv("GOOGLE_KEY_PATH")
WORKSHEET_NAME = "BulkMail"

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

EMAIL_SUBJECT = 'Your Daily Email Subject'
EMAIL_BODY = '''
Hello,

This is a test email.

Regards,
NGM Team
'''

MAX_EMAILS_PER_RUN = int(input("How many emails do you want to send this run? "))

# --- SETUP GOOGLE SHEET ---

def get_emails_from_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_KEY_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    data = sheet.get_all_records()
    
    # Add unique IDs for each email (using index) if not already present
    emails_with_id = []
    for idx, row in enumerate(data):
        if 'Email' in row:
            emails_with_id.append({
                'id': idx + 1,
                'email': row['Email'].strip()
            })
    return emails_with_id

# --- DATABASE SETUP ---

def init_db():
    conn = sqlite3.connect('sent_log.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sent_log (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE,
            date_sent TEXT
        )
    ''')
    conn.commit()
    conn.close()

def was_email_sent(email):
    conn = sqlite3.connect('sent_log.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM sent_log WHERE email = ?", (email,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_email_sent(email):
    conn = sqlite3.connect('sent_log.db')
    c = conn.cursor()
    today = datetime.today().strftime('%Y-%m-%d')
    c.execute("INSERT OR IGNORE INTO sent_log (email, date_sent) VALUES (?, ?)", (email, today))
    conn.commit()
    conn.close()

# --- EMAIL SENDER ---

def send_email(to_email):
    msg = MIMEText(EMAIL_BODY, 'plain')
    msg['Subject'] = EMAIL_SUBJECT
    msg['From'] = EMAIL_SENDER
    msg['To'] = to_email
    msg['Reply-To'] = EMAIL_SENDER  # Helps avoid spam
    msg['Return-Path'] = EMAIL_SENDER
    msg.add_header('X-Mailer', 'Python')

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
            print(f"✅ Sent to {to_email}")
            return True
    except Exception as e:
        print(f"❌ Failed to send to {to_email}: {e}")
        return False

# --- BULK MAILER MAIN ---

def run_bulk_mailer():
    init_db()
    emails = get_emails_from_sheet()

    print("📄 Emails read from Google Sheet:")
    for e in emails:
        print(f" - {e['email']}")

    unsent_emails = [e for e in emails if not was_email_sent(e['email'])]

    print("\n📬 Emails not yet sent:")
    if unsent_emails:
        for e in unsent_emails:
            print(f" - {e['email']}")
    else:
        print(" - None")

    if not unsent_emails:
        print("\n✅ All emails have already been sent.")
        return

    print(f"\n🚀 Sending to first {min(len(unsent_emails), MAX_EMAILS_PER_RUN)} emails...\n")

    to_send = unsent_emails[:MAX_EMAILS_PER_RUN]

    for record in to_send:
        if send_email(record['email']):
            mark_email_sent(record['email'])


if __name__ == "__main__":
    run_bulk_mailer()
