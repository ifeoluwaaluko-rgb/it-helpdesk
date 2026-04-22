import smtplib
from email.mime.text import MIMEText
from django.conf import settings

def send_email(subject, body, to_email):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = settings.DEFAULT_FROM_EMAIL
        msg['To'] = to_email

        if getattr(settings, 'EMAIL_USE_SSL', False):
            server = smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10)
        else:
            server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10)
            if getattr(settings, 'EMAIL_USE_TLS', False):
                server.starttls()

        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Email error: {e}")
