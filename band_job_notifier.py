import os
import smtplib
from email.message import EmailMessage

EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_TO = os.environ["EMAIL_TO"]

msg = EmailMessage()
msg["Subject"] = "Band Job Notifier Test Email"
msg["From"] = EMAIL_ADDRESS
msg["To"] = EMAIL_TO
msg.set_content(
    "Success! 🎶\n\nYour Band Job Notifier is now sending emails correctly."
)

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    server.send_message(msg)

print("Test email sent successfully.")

