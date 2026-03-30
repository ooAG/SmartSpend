import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime, timedelta

def send_alert(recipient_email, bill_details):
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = "temp65951@gmail.com" 
    SEND_AS = "no-reply@adarsh.eu.org"
    SENDER_PASSWORD = "anco wgvl lhzy nucg" 
    
    subject = "💳 SmartSpend: Unpaid Bill Summary"

    bill_list_str = ""
    for title, amount, due_date, status in bill_details:
        bill_list_str += f"- [{status}] {title}: ₹{amount} (Due: {due_date})\n"

    body = f"Hi,\n\nHere is a summary of your unpaid bills in SmartSpend:\n\n{bill_list_str}\nPlease log in to the dashboard to update your records."
    
    # ✨ FIX 1: Use MIMEText to handle UTF-8/Emojis correctly
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = SEND_AS
    msg['To'] = recipient_email
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SEND_AS, recipient_email, msg.as_string())
        server.quit()
        print(f"✅ Summary alert sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

# ✨ FIX 2: Open DB in Read-Only mode to prevent "Database is Locked" errors
# URI mode allows us to specify 'ro' (read-only)
db_path = "/home/ubuntu/SmartSpend/test.db"
try:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cursor = conn.cursor()

    today_str = datetime.now().strftime('%Y-%m-%d')
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    cursor.execute("""
        SELECT u.email, r.title, r.amount, r.due_date 
        FROM reminders r 
        JOIN users u ON r.user_id = u.id 
        WHERE r.is_paid = 0 
        ORDER BY u.email, r.due_date ASC
    """)

    rows = cursor.fetchall()
    user_reminders = {}

    for email, title, amount, due_date in rows:
        status_label = ""
        if due_date == tomorrow_str:
            status_label = "DUE TOMORROW"
        elif due_date <= today_str:
            status_label = "OVERDUE"
        
        if status_label:
            if email not in user_reminders:
                user_reminders[email] = []
            user_reminders[email].append((title, amount, due_date, status_label))

    for email, bills in user_reminders.items():
        send_alert(email, bills)

except sqlite3.OperationalError as e:
    print(f"❌ DB Access Error: {e}. Check if path is correct or DB is heavily swamped.")
finally:
    if 'conn' in locals():
        conn.close()
