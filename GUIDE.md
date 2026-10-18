# JARVIS — Beginner's Guide

Everything you need to install, run, understand, test, connect, deploy and show off JARVIS. Read it top to bottom the first time; after that, jump to the section you need.

**Contents**
0. The big picture
1. Install the tools
2. Run JARVIS on your computer
3. What each file does
4. Test the features
5. Put it on GitHub
6. Connect your services (cloud database, Canvas, AI brain, email, phone)
7. Deploy it (phone + computer)
8. Turn on automatic monitoring and alerts
9. How the Buy / Hold / Avoid ratings work
10. Voice tips
11. Add it to your portfolio
12. Troubleshooting

---

## 0. The big picture

```
            You (phone or laptop browser, typing or talking)
                              │
   ┌──────────────────────────▼───────────────────────────┐
   │  Streamlit pages (views/)                             │  what you see and click
   │  Dashboard · Ask JARVIS · School · Tasks · Calendar   │
   │  Investments · Settings                               │
   └───────┬───────────────┬───────────────┬──────────────┘
           │               │               │
   ┌───────▼──────┐ ┌──────▼───────┐ ┌─────▼────────────┐
   │ assistant.py │ │ research.py  │ │ canvas.py        │  the "skills"
   │ chat + voice │ │ signals.py   │ │ pulls homework   │
   │ (Claude AI)  │ │ market.py    │ │ from Canvas      │
   └───────┬──────┘ └──────┬───────┘ └─────┬────────────┘
           └───────────────┼───────────────┘
                   ┌───────▼───────┐
                   │    db.py      │  saves everything
                   └───────┬───────┘
          SQLite file on your laptop  ─or─  Supabase cloud database

   monitor.py ── runs on a schedule (GitHub Actions) ──► email / phone alerts
```

- **Streamlit** turns Python scripts into a website. `st.button("Save")` draws a button. No HTML or JavaScript needed.
- **SQLite / Supabase** store your data. SQLite is a single file on your computer. Supabase is a free cloud database, so your data survives when the online app restarts.
- **yfinance** downloads free daily price history for stocks, ETFs, crypto and gold.
- **Claude (optional)** is the AI "brain" that understands free-form sentences and decides which tool to use, like "add a quiz" or "rate VOO". Without it, JARVIS still works with a set of basic commands.
- **GitHub Actions** is a free robot that runs `monitor.py` every couple of hours and sends you alerts.

**JARVIS never buys or sells anything.** It has no connection to Fidelity or Robinhood. It only reads public prices and gives suggestions you can act on yourself.

---

## 1. Install the tools (one time)

1. **Python 3.10 or newer** from python.org. On Windows, tick **"Add Python to PATH"** during install. Check that it worked:
   ```bash
   python --version
   ```
   On Mac or Linux, use `python3` everywhere this guide says `python`.
2. **VS Code** (code.visualstudio.com) plus its **Python** extension.
3. **Git** (git-scm.com). Check with `git --version`.

> **What's a terminal?** A text window where you type commands. In VS Code: **Terminal → New Terminal**.

---

## 2. Run JARVIS on your computer

1. Unzip `jarvis-assistant.zip` into, for example, `Documents/jarvis-assistant`.
2. In VS Code, choose **File → Open Folder…** and pick that folder, then open a terminal.
3. Create a **virtual environment**: a private box of libraries just for this project.
   ```bash
   python -m venv .venv
   ```
4. Turn the box on. Do this every time you open a new terminal:
   ```bash
   # Windows
   .venv\Scripts\activate
   # Mac / Linux
   source .venv/bin/activate
   ```
   You'll see `(.venv)` at the start of the line.
5. Install the libraries:
   ```bash
   pip install -r requirements-dev.txt
   ```
6. Start JARVIS:
   ```bash
   streamlit run app.py
   ```
   Your browser opens **http://localhost:8501**. To stop the app, press **Ctrl + C** in the terminal.

**Try it on your phone (same Wi-Fi):** open the *Network URL* Streamlit prints, for example `http://192.168.1.23:8501`.

**Try it with fake prices** (useful when the market is closed or you're offline):
```bash
# Windows PowerShell
$env:JARVIS_FAKE_MARKET=1; streamlit run app.py
# Mac / Linux
JARVIS_FAKE_MARKET=1 streamlit run app.py
```

---

## 3. What each file does

| File | In plain English |
|---|---|
| `app.py` | The front door. Builds the sidebar menu (JARVIS / Life / Money / System). |
| `jarvis/db.py` | The memory. Defines every table, plus `add`, `update`, `delete`, settings, and the daily briefing. Uses your laptop's SQLite file, or Supabase when `DATABASE_URL` is set. |
| `jarvis/config.py` | Reads secrets (passwords, keys) from your environment or `.streamlit/secrets.toml`. |
| `jarvis/canvas.py` | Talks to Canvas, downloads assignments from every active course, guesses Test/Quiz/Assignment, and marks submitted work as done. |
| `jarvis/market.py` | Downloads price history (yfinance) and cleans up symbols (`btc` → `BTC-USD`, `gold` → `GC=F`). |
| `jarvis/signals.py` | The investment analyst. Computes trends, momentum, dips, RSI and volatility, then a Buy/Hold/Avoid rating **with reasons**. |
| `jarvis/research.py` | Combines your watchlist, holdings and profile; imports Fidelity CSVs; computes portfolio value. |
| `jarvis/alerts.py` | Sends email (Gmail) and phone push notifications (ntfy app). |
| `jarvis/monitor.py` | The night watchman. Syncs Canvas, checks prices, rating changes, price targets, due dates and reminders, then sends alerts. Never sends the same alert twice. |
| `jarvis/assistant.py` | The conversation brain. Basic command mode plus Claude AI mode with "tools" (functions the AI can call). |
| `jarvis/voice.py` | Turns your recorded voice into text, and turns replies into speech. |
| `jarvis/ui.py` | Shared look: header, colored pills, buttons, password lock, cached market data. |
| `views/*.py` | One file per page. |
| `tests/` | 60 automated checks. |
| `.github/workflows/tests.yml` | Runs the tests on GitHub every time you push. |
| `.github/workflows/monitor.yml` | Runs the monitor on a schedule and sends alerts. |

### Key ideas

**Tables** (like spreadsheet tabs): `school_items`, `study_sessions`, `tasks`, `events`, `reminders`, `watchlist`, `holdings`, `price_alerts`, `settings`, `alert_log`.

**One function saves anything:**
```python
db.add("tasks", title="Update resume", priority="High", due_date=date(2026, 10, 20))
```

**Tools for the AI.** In `assistant.py`, `TOOL_SPECS` describes functions like `add_task` and `analyze_asset`. When you say "I have a quiz in Linear Algebra next Friday", Claude replies, in effect, "call `add_school_item` with course=Linear Algebra, kind=Quiz, due_date=2026-10-23". The code runs that function, sends the result back, and Claude answers you. This loop is what people mean by **agentic AI**.

**Reruns.** Streamlit re-runs a page's script on every click, which is why the code calls `st.rerun()` after saving.

**Time zone.** Cloud servers use UTC. JARVIS always uses Pacific time, and you can change it with `JARVIS_TZ`.

---

## 4. Test the features

### Automatic tests
```bash
pytest
```
You should see **60 passed**. These tests use fake prices and fake Canvas data, so they work offline.

### Hands-on checklist
1. **School:** add a quiz due in 2 days. It appears on the Dashboard and in the briefing.
2. **Tasks:** add a task due today, then click **Done**.
3. **Calendar:** add an event today, and a reminder for 2 minutes from now. Refresh after 2 minutes.
4. **Investments → 🛠️:** click **Add a starter watchlist**. Open **🧭 Ratings** and expand **Why this rating?**
5. Add a holding (for example VOO, 2 shares, $480), then check **💼 Portfolio**.
6. **Ask JARVIS:** type `what's due this week`, `add task call the bank tomorrow`, `remind me to study at 7pm`, `should I buy VOO?`. Then tap 🎤 and say "what are my tasks".
7. **Settings → 🔔 Alerts → Run a dry run** shows what the monitor would send right now.
8. Stop and restart the app. Your data is still there.

> I tested everything with simulated prices. My build machine couldn't reach Yahoo Finance, so do step 4 once without `JARVIS_FAKE_MARKET` to confirm live prices load on your network.

---

## 5. Put it on GitHub

1. On github.com, click **New repository**, name it `jarvis-assistant`, make it **Public**, and **don't** add a README. Click **Create**.
2. In the project terminal:
   ```bash
   git init
   git add .
   git commit -m "JARVIS: school, tasks, calendar, investments, alerts, voice"
   git branch -M main
   git remote add origin https://github.com/Andrew-742001/jarvis-assistant.git
   git push -u origin main
   ```
3. Later changes: `git add .` → `git commit -m "what changed"` → `git push`.

`.gitignore` keeps your database and `secrets.toml` off GitHub. **Never** commit passwords or tokens.

---

## 6. Connect your services

Each service is optional, and JARVIS shows what's connected under **Settings → 🧩 System**. Put every secret in **`.streamlit/secrets.toml`** on your computer: copy `.streamlit/secrets.toml.example` and fill it in. Online, the same lines go into the app's **Secrets** box.

### 6a. Cloud database: Supabase (free) — makes data permanent online
1. Sign up at **supabase.com** and click **New project**. Pick a region near California and save the database password.
2. Click **Connect** (top of the project page), then **Connection string**, then choose **Session pooler**. Copy the URI and replace `[YOUR-PASSWORD]` with your password.
3. Add it to your secrets:
   ```toml
   DATABASE_URL = "postgresql://postgres.abcd:YOURPASSWORD@aws-0-us-west-1.pooler.supabase.com:5432/postgres"
   ```
4. Restart JARVIS. It creates all the tables by itself. Settings should now say *cloud database*.

Your laptop and the online app can share this same database, so everything stays in sync.

### 6b. Canvas
1. Log in to Canvas, then go to **Account → Settings → Approved Integrations → + New Access Token**. Name it `JARVIS`, then copy the token. It's shown only once.
2. Add to your secrets:
   ```toml
   CANVAS_URL = "https://yourcollege.instructure.com"
   CANVAS_TOKEN = "the-token"
   ```
   Use the address you see in your browser's address bar when you're on Canvas, up to `.com`.
3. Go to **School** or **Settings** and click **Sync Canvas**. Quizzes and exams get High priority, and submitted work is marked done. Items you mark done yourself stay done.

If the **New Access Token** button is missing, your college has disabled tokens, so keep adding work by hand.

### 6c. AI brain: Claude (optional, pay-as-you-go)
1. Go to **console.anthropic.com**, add a small amount of credit, then **API Keys → Create Key**.
2. Add to your secrets:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
   JARVIS uses the fast, inexpensive `claude-haiku-5-5` model by default. Set `JARVIS_MODEL = "claude-sonnet-5-5"` for a smarter one.

Without a key, JARVIS uses basic commands such as `add task …`, `add quiz for COURSE: TITLE on friday`, `remind me to … at 7pm`, `add event … on 10/24 at 3pm`, `should I buy VOO?`, `how is my portfolio`, `what's due`, and `briefing`.

### 6d. Email alerts: Gmail
1. Turn on **2-Step Verification** for your Google account.
2. Go to **myaccount.google.com/apppasswords**, create an app password called `JARVIS`, and copy the 16 characters.
3. Add to your secrets:
   ```toml
   SMTP_USER = "you@gmail.com"
   SMTP_PASSWORD = "abcd efgh ijkl mnop"
   ALERT_EMAIL_TO = "you@gmail.com"
   ```

### 6e. Phone alerts: ntfy (free, no account)
1. Install the **ntfy** app (iPhone or Android).
2. Make up a long, random topic name, like `jarvis-andrew-k29fq81`. Anyone who knows the name can read it, so make it hard to guess.
3. In the app, tap **+** and subscribe to that topic.
4. Add to your secrets:
   ```toml
   NTFY_TOPIC = "jarvis-andrew-k29fq81"
   ```
5. Go to **Settings → 🔔 Alerts → Send a test alert**. Your phone should buzz.

### 6f. Password lock
```toml
APP_PASSWORD = "something-strong"
```
Strongly recommended once your real data and holdings live online.

---

## 7. Deploy it (phone + computer)

1. Go to **share.streamlit.io**, sign in with GitHub, then **Create app → Deploy a public app from GitHub**.
2. Repository `Andrew-742001/jarvis-assistant`, branch `main`, main file `app.py`. Pick a URL like `andrew-jarvis`.
3. Open **Advanced settings → Secrets** and paste **everything** from your local `secrets.toml`.
4. Click **Deploy**. On your phone, open the link, then **Share → Add to Home Screen**.

Every `git push` redeploys automatically. To change secrets later, go to your app, then **⋮ → Settings → Secrets**.

---

## 8. Automatic monitoring and alerts

The file `.github/workflows/monitor.yml` tells GitHub to run `python -m jarvis.monitor`:
- **every 2 hours from about 7 AM to 3 PM Pacific** (an hour earlier in winter, since GitHub uses UTC), for price moves, rating changes, price targets, due tomorrow, tests within 3 days, and reminders;
- **at about 7:47 AM every day**, a full **daily briefing** (your day plus a market check).

Turn it on:
1. On GitHub, open your repo, then **Settings → Secrets and variables → Actions → New repository secret**.
2. Add each of these that you use: `DATABASE_URL` (**required**, so the robot sees the same data as your app), `CANVAS_URL`, `CANVAS_TOKEN`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO`, `NTFY_TOPIC`.
3. Go to the **Actions** tab, choose **jarvis-monitor**, then **Run workflow** to test it right away. Tick *digest* to receive the full briefing.

Notes:
- Change how big a daily move triggers an alert in **Settings → Profile**. Set price targets in **Investments → 🎯**.
- GitHub may start scheduled runs a few minutes late, and it pauses schedules after 60 days with no commits. Push any small change to wake it up.
- Test locally without sending anything: `python -m jarvis.monitor --dry-run`.

---

## 9. How the Buy / Hold / Avoid ratings work

JARVIS adds up points from simple, well-known signals. Every point shows up as a reason you can read.

| Signal | What it means | Points |
|---|---|---|
| Price vs 200-day average | Above = long-term uptrend | +1 / −1 |
| 50-day vs 200-day average | Short-term momentum agrees with the trend | +0.5 / −0.5 |
| Pullback 5–20% from the 52-week high, still in an uptrend | "On sale" within a healthy trend | +1 |
| More than 30% below the 52-week high | Deep slump | −1 |
| RSI under 30 / over 70 | Oversold (maybe overdone) / overbought (maybe wait) | +0.5 / −0.5 |
| Volatility above your comfort zone | Conservative 20%, Moderate 35%, Aggressive 70% per year | −1 |
| Broad index fund (VOO, SPY, VTI…) with a 5+ year horizon | Diversified and historically rewarding for long-term investors | +1.5 |
| One holding is more than 25% of your portfolio | Concentration risk | −1 |

**Score ≥ 2 → Buy**, **≤ −1.5 → Avoid**, otherwise **Hold**. Broad index funds are never rated Avoid, because for long-term investors, steady investing has historically beaten trying to time the market.

**Be honest with yourself about what this is.** These are explainable research signals based on past prices, not predictions. They don't know about earnings, news, or your full financial picture. Use them to decide what to look into, then make the final call yourself. For your long-term money, the boring answer (keep buying a broad index fund like VOO regularly) is usually the right one.

---

## 10. Voice tips

- Open **Ask JARVIS**, tap **🎤**, speak, then tap stop. JARVIS transcribes it, answers, and speaks the reply.
- The first time, allow microphone access. Chrome and Safari both work.
- Some phones block automatic speech. If you hear nothing, tap play on the small audio player under the reply.
- Speech-to-text uses Google's free recognizer, so it needs internet.

---

## 11. Add it to your portfolio

`docs/portfolio-card.html` is a ready-to-paste project card for andrew-742001.github.io. Copy `docs/dashboard.png` into your portfolio's images folder and replace `YOUR-APP` with your Streamlit URL. Then pin `jarvis-assistant` on your GitHub profile (**Customize your pins**).

---

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| `python` / `streamlit` not found | Use `python3`; turn on the virtual environment (step 2.4). |
| Windows blocks activating `.venv` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once in PowerShell. |
| Investments shows "No price data" | Check the ticker (crypto = `BTC-USD`). Yahoo occasionally rate-limits, so wait 15 minutes. |
| Canvas: "rejected the token" | Make a new token; check `CANVAS_URL` has no `/courses/...` on the end. |
| Supabase connection error | Use the **Session pooler** string and replace `[YOUR-PASSWORD]`. |
| Gmail "Username and Password not accepted" | Use an **app password**, not your normal password. |
| Voice "couldn't make out any words" | Speak closer to the mic; check that the browser has mic permission. |
| Deployed app error | On share.streamlit.io, go to **Manage app** and read the logs. |
| Start fresh locally | Stop the app and delete `data/jarvis.db`. |
