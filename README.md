# Interview Page Watcher

Watches and emails you (with a
screenshot) the moment the page's content changes — including when the
interview calendar opens up available slots.

## How it works

- The interview calendar on that page is loaded by JavaScript, not present
  in the raw HTML. So this uses [Playwright](https://playwright.dev/) to
  render the page in a real (headless) browser, the same way you'd see it.
- It reads all visible text on the page, hashes it, and compares it to the
  hash from the last run (stored in `state.json`).
- If the text changed, it emails you a diff of what changed plus a
  full-page screenshot, so you can see at a glance if slots opened.
- It runs on a schedule via GitHub Actions — no server of your own needed.

## Setup (10 minutes)

### 1. Create the repo

Create a **public** GitHub repo (public = free, unlimited Actions minutes)
and push these files to it.

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

### 2. Get email-sending credentials

Easiest option: a Gmail account with an **App Password**.

1. Turn on 2-Step Verification on the Google account you'll send *from*:
   https://myaccount.google.com/security
2. Create an App Password: https://myaccount.google.com/apppasswords
   (choose "Mail" as the app). Copy the 16-character password.
3. You don't need a new account — you can use your own Gmail and send the
   alert to that same address, or to any other email address.

Any SMTP provider works (Outlook, iCloud, SendGrid, etc.) — just adjust the
server/port below.

### 3. Add GitHub Secrets

In your repo: **Settings → Secrets and variables → Actions → New repository secret**.
Add each of these:

| Secret name    | Example value                  | Notes                                   |
|-----------------|--------------------------------|------------------------------------------|
| `SMTP_SERVER`   | `smtp.gmail.com`               | Gmail's SMTP server                     |
| `SMTP_PORT`     | `587`                          | STARTTLS port                           |
| `SMTP_USER`     | `youraddress@gmail.com`        | The account you made the App Password for |
| `SMTP_PASS`     | `xxxx xxxx xxxx xxxx`          | The 16-character App Password           |
| `EMAIL_FROM`    | `youraddress@gmail.com`        | Can be same as SMTP_USER                |
| `EMAIL_TO`      | `youraddress@gmail.com`        | Where you want the alert sent           |

### 4. Turn it on

The workflow (`.github/workflows/check.yml`) is already scheduled to run
every 10 minutes. You can also trigger it manually: go to the **Actions**
tab → **Check HMC interview page** → **Run workflow**.

The **first run** just saves a baseline (no email sent). Every run after
that compares against the baseline and emails you if anything changed.

## Notes & limitations

- **Timing:** GitHub's cron scheduler has a 5-minute minimum interval and
  isn't perfectly real-time — runs can lag a few minutes behind,
  especially at busy times (e.g. right at the top of the hour). Treat this
  as "within a few minutes," not "the literal second."
- **Keeping it alive:** GitHub automatically disables scheduled workflows
  in a repo that's had no commits for 60 days. The workflow commits
  `state.json` back on every run (even "no change" runs refresh a
  timestamp), which counts as activity and prevents that.
- **False positives:** if HMC's site has any rotating/dynamic content
  unrelated to the calendar (ads, a "last updated" timestamp, etc.), you
  might get a noisy alert. If that happens, tell me what changed and I can
  tighten `monitor.py` to ignore that specific bit of the page, or to only
  watch the calendar section specifically.
- **Local testing:** you can also run this on your own machine before
  pushing to GitHub:
  ```bash
  pip install -r requirements.txt
  playwright install chromium
  export SMTP_SERVER=smtp.gmail.com SMTP_PORT=587 \
         SMTP_USER=... SMTP_PASS=... EMAIL_FROM=... EMAIL_TO=...
  python monitor.py
  ```
