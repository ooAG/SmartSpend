import random
import smtplib
from email.mime.text import MIMEText

OTP_STORE = {}  # temp in-memory (use Redis in real world)

def generate_otp(email):
    otp = str(random.randint(100000, 999999))
    OTP_STORE[email] = otp
    return otp

def verify_otp(email, otp):
    return OTP_STORE.get(email) == otp

def send_email_otp(email, otp):
    msg = MIMEText(f"Your OTP is {otp}")
    msg['Subject'] = 'Login OTP'
    
    # 1. PUT YOUR ACTUAL GMAIL HERE
    SENDER_EMAIL = "temp65951@gmail.com" 
    SEND_AS = "no-reply@adarsh.eu.org"
    # 2. PUT YOUR 16-CHARACTER APP PASSWORD HERE
    APP_PASSWORD = "anco wgvl lhzy nucg" 

    msg['From'] = SEND_AS
    msg['To'] = email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)