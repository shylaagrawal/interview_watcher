#!/usr/bin/env python3
"""
Watches https://connect.hmc.edu/portal/hmc-interview for changes
(especially the interview calendar opening up) and emails you when
something changes.

Why a headless browser: the calendar on that page is rendered by
JavaScript after the initial page load, so a plain HTTP GET request
won't see real availability data. Playwright loads the page the same
way a real browser/visitor would, then we read the rendered text.

State (the last-seen content hash/text) is stored in state.json so
the diff persists across runs. In GitHub Actions, the workflow commits
that file back to the repo after each run.
"""

import hashlib
import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from difflib import unified_diff
from email.message import EmailMessage
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://connect.hmc.edu/portal/hmc-interview"
STATE_FILE = Path("state.json")
SCREENSHOT_FILE = Path("screenshot.png")

# How long to let the page sit after "networkidle" before we read it,
# to give the calendar widget time to finish rendering.
EXTRA_WAIT_MS = 4000


def fetch_rendered_page():
    """Load the page in a real browser and return (visible_text, screenshot_bytes)."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 2000})
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(EXTRA_WAIT_MS)

        # Grab all visible text on the page. This naturally picks up
        # calendar day cells, the legend, and everything else, without
        # us having to guess exact CSS class names for "available" days.
        text = page.evaluate("document.body.innerText")

        screenshot_bytes = page.screenshot(full_page=True)

        browser.close()
        return text, screenshot_bytes


def normalize(text: str) -> str:
    """Strip volatile noise (blank lines, trailing whitespace) so we don't
    get false-positive diffs from irrelevant whitespace changes."""
    lines = [line.rstrip() for line in text.splitlines()]
    lines = [line for line in lines if line.strip() != ""]
    return "\n".join(lines)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return None


def save_state(text: str):
    state = {
        "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    STATE_FILE.write_text(json.dumps(state, indent=2))


def send_email(subject: str, body: str, screenshot_bytes: bytes | None):
    smtp_server = os.environ["SMTP_SERVER"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    email_from = os.environ.get("EMAIL_FROM", smtp_user)
    email_to = os.environ["EMAIL_TO"]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content(body)

    if screenshot_bytes:
        msg.add_attachment(
            screenshot_bytes,
            maintype="image",
            subtype="png",
            filename="calendar_screenshot.png",
        )

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def main():
    print(f"Checking {URL} ...")
    raw_text, screenshot_bytes = fetch_rendered_page()
    current_text = normalize(raw_text)
    current_hash = hashlib.sha256(current_text.encode("utf-8")).hexdigest()

    SCREENSHOT_FILE.write_bytes(screenshot_bytes)

    previous = load_state()

    if previous is None:
        print("No previous state found. Saving baseline, not sending an email.")
        save_state(current_text)
        return

    if previous["hash"] == current_hash:
        print("No change detected.")
        # Still refresh checked_at so the repo has recent activity
        # (keeps GitHub from auto-disabling the scheduled workflow).
        save_state(current_text)
        return

    print("CHANGE DETECTED. Sending email...")

    diff = "\n".join(
        unified_diff(
            previous["text"].splitlines(),
            current_text.splitlines(),
            fromfile="previous",
            tofile="current",
            lineterm="",
        )
    )
    if not diff.strip():
        diff = "(Content changed but no line-level diff was produced — check the screenshot.)"

    body = (
        f"The HMC interview page changed: {URL}\n\n"
        f"Checked at: {datetime.now(timezone.utc).isoformat()}\n\n"
        f"---- What changed (unified diff) ----\n"
        f"{diff}\n\n"
        f"A current screenshot of the page is attached.\n"
    )

    try:
        send_email(
            subject="HMC interview page changed!",
            body=body,
            screenshot_bytes=screenshot_bytes,
        )
        print("Email sent.")
    except Exception as e:
        print(f"Failed to send email: {e}", file=sys.stderr)
        save_state(current_text)
        raise

    save_state(current_text)


if __name__ == "__main__":
    main()
