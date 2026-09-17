"""
Central configuration for the e-book ethio cs bot.
All values are loaded from environment variables in the local .env file or
from Railway service variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Comma-separated list of Telegram user IDs allowed to use admin commands
# e.g. ADMIN_IDS=123456789,987654321
_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()}

# Text shown to a buyer after they tap "Buy" — put your bank account / mobile
# money / crypto wallet details here. Edit this in .env, not in code, so you
# can update it any time without redeploying.
_default_instructions = (
    "💳 እባክዎ ክፍያዎን ከሚከተሉት በአንዱ ይላኩ፦\n\n"
    "🏦 CBE: 1000543473735\n"
    "🏦 Bank of Abyssinia: 136646238\n"
    "📱 Telebirr: 0911410963\n"
    "\n"
    "👉 ቁጥሮቹን በመንካት በቀላሉ ኮፒ ማድረግ ይችላሉ!\n\n"
    "✅ ክፍያውን ከፈጸሙ በኋላ ከታች ያለውን ከፈልኩ የሚለውን ይጫኑ እና የክፍያ ማረጋገጫ ስክሪንሾት ይላኩልን።\n\n"
    "📞 ክፍያ ሲፈጽሙ ማንኛውም አይነት ችግር ከገጠመዎ ወይም ያልገባዎት ነገር ካለ 0911410963 ቀጥታ መደወል ይችላሉ!"
)
# .env files store literal text, so a real newline can't live inside one
# value — we write \n in .env and turn it back into a real newline here.
PAYMENT_INSTRUCTIONS = os.getenv("PAYMENT_INSTRUCTIONS", _default_instructions).replace("\\n", "\n")

DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "ETB")
DB_PATH = os.getenv("DB_PATH", "ebook_catalog.db")

# Brand / app identity. Change these in .env for a brother-specific version.
BOT_NAME = os.getenv("BOT_NAME", "e-book ethio cs")
BOT_TAGLINE = os.getenv(
    "BOT_TAGLINE",
    "ህይወትዎን የሚቀይሩ በጥራት የተዘጋጁ ዲጂታል መጽሐፍትን ለማግኘት start የሚለውን ይጫኑ !"
)

BOOKS_PER_PAGE = 5

# Optional ebook follow-up reminders. Times use 24-hour HH:MM format.
REMINDER_TIMEZONE = os.getenv("REMINDER_TIMEZONE", "Africa/Addis_Ababa")
REMINDER_DAY_TIME = os.getenv("REMINDER_DAY_TIME", "09:00")
REMINDER_NIGHT_TIME = os.getenv("REMINDER_NIGHT_TIME", "20:00")
REMINDER_TIMES = os.getenv("REMINDER_TIMES", "")
REMINDER_INTERVAL_HOURS = int(os.getenv("REMINDER_INTERVAL_HOURS", "10"))
REMINDER_MAX_PER_BOOK = int(os.getenv("REMINDER_MAX_PER_BOOK", "6"))

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is not set. Add it to the local .env file or Railway variables."
    )
if not ADMIN_IDS:
    print(
        "WARNING: No ADMIN_IDS configured. Nobody will be able to add books "
        "or approve orders. Set ADMIN_IDS in your .env file."
    )
