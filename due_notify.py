# /home/ubuntu/SmartSpend/bill_checker.py
import sqlite3
import smtplib
from datetime import datetime, timedelta

def send_alert(recipient_email, bill_details):
    """
    Sends a consolidated reminder for upcoming and overdue bills.
    bill_details: List of tuples (title, amount, due_date, status_label)
    """
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = "temp65951@gmail.com" 
    # Note: Gmail only allows SEND_AS if it's an authorized alias in settings
    SEND_AS = "no-reply@adarsh.eu.org"
    SENDER_PASSWORD = "anco wgvl lhzy nucg" 
    
    subject = "💳 SmartSpend: Unpaid Bill Summary"

    bill_list_str = ""
    for title, amount, due_date, status in bill_details:
        bill_list_str += f"- [{status}] {title}: ₹{amount} (Due: {due_date})\n"

    body = f"Hi,\n\nHere is a summary of your unpaid bills in SmartSpend:\n\n{bill_list_str}\nPlease log in to the dashboard to update your records."
    
    # Constructing the message with headers
    msg = f"From: {SEND_AS}\nTo: {recipient_email}\nSubject: {subject}\n\n{body}"
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.set_debuglevel(0)
        server.starttls()
        # ✨ FIX: Always login with the actual Gmail address, not the alias
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SEND_AS, recipient_email, msg)
        server.quit()
        print(f"✅ Summary alert sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

# Database connection
db_path = "/home/ubuntu/SmartSpend/test.db" [cite: 1]
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Define the timeframe: Today and Tomorrow
today_dt = datetime.now()
today_str = today_dt.strftime('%Y-%m-%d')
tomorrow_str = (today_dt + timedelta(days=1)).strftime('%Y-%m-%d')

# 2. SQL: Get all unpaid bills (is_paid = 0) sorted by user 
cursor.execute("""
    SELECT u.email, r.title, r.amount, r.due_date 
    FROM reminders r 
    JOIN users u ON r.user_id = u.id 
    WHERE r.is_paid = 0 
    ORDER BY u.email, r.due_date ASC
""")

rows = cursor.fetchall()

# 3. Logic: Filter and Label (Overdue vs. Due Tomorrow)
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

# 4. Dispatch Emails
for email, bills in user_reminders.items():
    send_alert(email, bills)

conn.close()
