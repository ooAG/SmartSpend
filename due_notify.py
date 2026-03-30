# /home/ubuntu/SmartSpend/bill_checker.py
import sqlite3
import smtplib
from datetime import datetime, timedelta

def send_alert(recipient_email, bill_details):
    """
    Sends a reminder for one or more bills.
    bill_details: List of tuples (title, amount, due_date)
    """
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = "temp65951@gmail.com" 
    SEND_AS = "no-reply@adarsh.eu.org"
    # 2. PUT YOUR 16-CHARACTER APP PASSWORD HERE
    SENDER_PASSWORD = "anco wgvl lhzy nucg" 

    subject = "💳 SmartSpend: Upcoming Bill Reminders"
    
    # Build a list of all due bills for this specific user
    bill_list_str = ""
    for title, amount, due_date in bill_details:
        bill_list_str += f"- {title}: ₹{amount} (Due: {due_date})\n"

    body = f"Hi,\n\nThis is a reminder for your upcoming unpaid bills:\n\n{bill_list_str}\nLog in to SmartSpend to manage your payments."
    msg = f"Subject: {subject}\n\n{body}"
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SEND_AS, recipient_email, msg)
        server.quit()
        print(f"✅ Alert sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

# Database connection
db_path = "/home/ubuntu/SmartSpend/test.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Sort and filter: Get all users who have unpaid bills (is_paid = 0)
# and include bill details for date checking.
tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

cursor.execute("""
    SELECT u.email, r.title, r.amount, r.due_date 
    FROM reminders r 
    JOIN users u ON r.user_id = u.id 
    WHERE r.is_paid = 0 
    ORDER BY u.email, r.due_date ASC
""")

rows = cursor.fetchall()

# 2. Group bills by user and check if the date is tomorrow
user_reminders = {}

for email, title, amount, due_date in rows:
    # Only keep the bill if it is due tomorrow
    if due_date == tomorrow:
        if email not in user_reminders:
            user_reminders[email] = []
        user_reminders[email].append((title, amount, due_date))

# 3. Send grouped reminders to each user
for email, bills in user_reminders.items():
    send_alert(email, bills)

conn.close()
