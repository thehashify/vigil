# Nivesh Co-Pilot

Your personal long-term investing dashboard for Indian stocks and index funds.

- **Home**: what your money is worth, what to do this month, today's news, and your holdings
- **Stock check**: a 0–10 scorecard and plain-English verdict for any NSE company
- **Find ideas**: ranks your watchlist or 50 large companies on the same checklist
- **My money**: enter your holdings, watchlist and monthly SIP plan
- **Learn**: the basics, and how to read the scores
- **Telegram alerts** (optional): a message on your phone only when something matters

Data is free: Yahoo Finance (prices about 15 minutes delayed, plus company financials), Google News, and mfapi.in for mutual fund NAVs.

> This is a personal tool. It is not advice from a SEBI-registered adviser. Scores come from simple rules and can be wrong. You make every decision.

---

## Put it online (one time, about 20 minutes, no coding)

You'll create two free accounts: **GitHub** (stores the app's files) and **Streamlit** (runs the app as a website).

### Step 1: Put the files on GitHub
1. Go to **github.com** and sign up (free).
2. Click the **+** at the top right → **New repository**.
3. Name it `nivesh-copilot`, choose **Private**, and click **Create repository**.
4. On the next page, click **uploading an existing file**.
5. Unzip `nivesh-copilot.zip` on your computer and drag **everything inside the folder** onto the page.
   - The `.github` and `.streamlit` folders are hidden on some computers. On Mac press `Cmd+Shift+.` to show them; on Windows tick *View → Hidden items*.
6. Click **Commit changes**.

### Step 2: Turn it into a website
1. Go to **share.streamlit.io** and click **Continue with GitHub**.
2. Click **Create app** → **Deploy a public app from GitHub**. Pick your `nivesh-copilot` repository, branch `main`, main file `app.py`.
3. Under **App URL**, pick a name you'll remember.
4. Click **Deploy**. After 2–3 minutes your app opens. Bookmark it on your phone.
5. **Make it private:** in the app, open **Settings → Sharing** and set it so only you (your email) can view it.

### Step 3: Enter your real investments
Open the **My money** tab:
- **Stocks**: type `stock`, the NSE symbol (e.g. `HDFCBANK`), number of shares and your average buy price. You'll find these in the Angel One app under *Portfolio → Holdings*.
- **Index/mutual funds**: type `fund`. Use *Find your fund's scheme code* to get the code, then enter your units and the total you've invested.
- Untick **Show example banner** and save your plan.

**Make saves permanent (recommended).** Without this, the app forgets your edits whenever Streamlit restarts it.
1. On GitHub, open **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Under *Repository access* choose **Only select repositories** → `nivesh-copilot`.
3. Under *Permissions*, set **Contents** to **Read and write**, then click **Generate token** and copy it.
4. In Streamlit, open your app's **Settings → Secrets** and paste:
   ```toml
   GITHUB_TOKEN = "paste-the-token-here"
   GITHUB_REPO = "your-github-username/nivesh-copilot"
   ```

---

## Optional extras

### AI news summaries (costs a little)
The AI turns headlines into a short, plain-English summary. Expect a few hundred rupees a month or less for one person.
1. Create an account at **console.anthropic.com**, add a small amount of credit, and create an API key.
2. Add it in Streamlit **Settings → Secrets**: `ANTHROPIC_API_KEY = "sk-ant-..."`
3. For Telegram alerts, also add it in GitHub (see below).

### Telegram alerts on your phone (free)
1. In Telegram, message **@BotFather**, send `/newbot`, and follow the steps. Copy the **token** it gives you.
2. Open your new bot and send it any message (e.g. "hi").
3. In a browser, open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and find `"chat":{"id":123456789`. That number is your **chat ID**.
4. On GitHub, open your repo → **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `TELEGRAM_BOT_TOKEN`: the token
   - `TELEGRAM_CHAT_ID`: the number
   - `ANTHROPIC_API_KEY` (optional): for AI summaries in alerts
5. To test it, go to the **Actions** tab → **Daily alerts** → **Run workflow**.

The job runs automatically at 6:45 PM IST on weekdays. It only messages you when:
- one of your stocks moves 5%+ down or 8%+ up in a day,
- a holding is marked *Review* or *Avoid* (Mondays only),
- a good watchlist company falls 10%+ in a month,
- the market falls 3%+ in a week,
- your SIP is due tomorrow,
- or it's the start of a month (monthly summary).

---

## How the scorecard works
Each company gets five scores out of 10:

| Score | What it checks |
|---|---|
| Business quality (30%) | Return on equity, profit margin, profit growth |
| Financial health (20%) | Debt vs equity and short-term cash (for banks: return on assets) |
| Price vs value (20%) | P/E, P/E vs growth, price vs its 5-year average |
| Recent trend (15%) | Price vs 50- and 200-day averages, 1-year change |
| News (15%) | Tone of the last 30 days of headlines |

**Verdicts:** *Add slowly* (strong company, fair price) · *Wait for a better price* · *Hold* · *Review* · *Avoid*.
All the rules are in `core/scoring.py`.

## Files
- `app.py`: the website
- `alerts.py` + `.github/workflows/alerts.yml`: the daily Telegram job
- `core/`: data fetching, scoring, AI summaries, saving
- `data/`: your portfolio, watchlist and plan
