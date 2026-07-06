"""Renders the briefing HTML and sends it via Gmail SMTP."""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()


def render_email(brief: dict) -> str:
    """Renders render/template.html with the brief dict, returns HTML string."""
    env = Environment(loader=FileSystemLoader("render"))
    template = env.get_template("template.html")
    return template.render(**brief)


def send_email(html_content: str, config: dict, date: str = "") -> bool:
    """Sends html_content via Gmail SMTP. Returns True on success, False on failure.

    date: value of brief["date"], used in the subject line. Passed separately
    since this function only receives the rendered HTML, not the brief dict.
    """
    try:
        gmail_address = os.environ["GMAIL_ADDRESS"]
        gmail_password = os.environ["GMAIL_APP_PASSWORD"]
        recipient = config["email"]["to"]

        msg = MIMEMultipart()
        msg["Subject"] = f"Daily Executive Briefing — {date}"
        msg["From"] = gmail_address
        msg["To"] = recipient
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(gmail_address, gmail_password)
            smtp.sendmail(gmail_address, recipient, msg.as_string())

        return True
    except Exception as e:
        # WHY: match project-wide style — log and return a failure signal, never raise.
        print(f"[mailer] failed to send email: {e}")
        return False
