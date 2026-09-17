# e-book ethio cs Telegram Bot

A ready-to-run Telegram bot for selling digital e-books with manual
(screenshot-based) payment approval. No payment gateway needed to start —
you approve orders yourself and the bot delivers the file automatically.

## How it works

**Buyers:** `/start` → Browse Books → pick a title → Buy → see your payment
instructions → pay → tap "I've Paid" → send a screenshot.

**You (admin):** get the screenshot instantly with Approve/Reject buttons.
Tap Approve and the bot sends the e-book file to the buyer automatically.

Adding new books is done entirely inside Telegram with `/addbook` — no code
editing needed as your catalog grows.

## 1. Create your bot

1. Open Telegram, message **@BotFather**, send `/newbot`, follow the prompts.
2. Copy the token it gives you (looks like `123456:ABC-...`).
3. Message **@userinfobot** to get your own numeric Telegram user ID — you'll
   need this to make yourself an admin.

## 2. Local setup

```bash
cd telegram-ebook-bot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
# Create a local .env file with the required bot, admin, payment, and database values.
```

Edit `.env`:
- `BOT_TOKEN` — from BotFather
- `ADMIN_IDS` — your Telegram user ID (comma-separated for multiple admins)
- `PAYMENT_INSTRUCTIONS` — your bank/mobile-money/crypto details shown to buyers

Run it:
```bash
python main.py
```

Message your bot on Telegram and send `/start`. As an admin, send `/addbook`
to add your first title (you'll be asked for title, description, price,
category, then to upload the actual file, then optionally a cover image).

## 3. Admin commands

| Command | What it does |
|---|---|
| `/addbook` | Guided flow to add a new e-book |
| `/listbooks` | View catalog with edit and delete buttons |
| `/stats` | Orders, pending count, revenue |

Regular buyers never see these — they're restricted to the IDs in `ADMIN_IDS`.

From `/listbooks`, tap **Edit** on any live book. You can update its title,
short description, detailed description, price, currency, category, e-book
file, or cover. Preview images can be removed one at a time or added without
deleting the existing images. Use `/remove` while editing the cover to remove
it completely.

## 4. Hosting it 24/7

Since you don't have hosting yet, here are your best options, easiest first:

### Option A — Railway.app (recommended for starting out)
Free/cheap, zero server management, deploys straight from a GitHub repo.

1. Push this folder to a GitHub repo (make it **private** — it can contain
   your bot token if you're not careful with `.env`; better yet, never commit
   `.env` at all — see `.gitignore` note below).
2. Go to railway.app → New Project → Deploy from GitHub repo.
3. In Railway's dashboard, add environment variables (`BOT_TOKEN`,
   `ADMIN_IDS`, `PAYMENT_INSTRUCTIONS`, etc.) under the Variables tab —
   don't upload your `.env` file itself.
4. Set the start command to `python main.py`.
5. **Important:** Railway's filesystem is ephemeral on redeploys unless you
   attach a volume. Add a persistent volume mounted at, say, `/data`, and set
  `DB_PATH=/data/ebook_catalog.db` in your env vars so your catalog and orders
   survive restarts.

### Option B — Render.com
Similar to Railway — "Background Worker" service type (not "Web Service",
since this bot doesn't listen on a port by default). Same env var and volume
notes apply.

### Option C — A cheap VPS (Hetzner, DigitalOcean, etc.), ~$4-6/month
More control, no ephemeral-storage surprises.

```bash
# on the server
sudo apt update && sudo apt install -y python3-venv git
git clone <your-repo-url>
cd telegram-ebook-bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Create and edit the local .env file with nano/vim.
```

Keep it running permanently with `systemd`:

```ini
# /etc/systemd/system/ebookbot.service
[Unit]
Description=e-book ethio cs Telegram bot
After=network.target

[Service]
WorkingDirectory=/home/youruser/telegram-ebook-bot
ExecStart=/home/youruser/telegram-ebook-bot/venv/bin/python main.py
Restart=always
User=youruser

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ebookbot
sudo systemctl start ebookbot
sudo systemctl status ebookbot   # check it's running
```

## 5. Security notes

- Never commit your real `.env` file to a public repo — it contains your bot
  token, which gives full control of your bot to anyone who has it.
- Back up `ebook_catalog.db` periodically (it's a single SQLite file) — it holds your
  entire catalog and order history.
- Since payment approval is manual, only approve orders after you've actually
  verified the payment landed in your account — screenshots can be faked.

## 6. Where this can grow later

The code is deliberately simple and flat (5 files) so it's easy to extend:
- Swap manual approval for **Telegram Payments / Stripe** later — the
  `buy` → `paid` flow in `handlers_user.py` is the only place that changes.
- Add discount codes, categories with sub-tags, or a search command.
- Move from SQLite to Postgres if your catalog or order volume gets large —
  `db.py` is the only file that touches the database, so the rest of the
  bot won't need to change.
