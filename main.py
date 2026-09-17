"""
E-book ethio cs bot — entry point.
Run with: python main.py
"""
import asyncio
import logging

from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
)

from config import BOT_TOKEN
import db
import handlers_user as u
import handlers_admin as a

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# Telegram HTTP request logs can include the bot token in their URL.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main():
    asyncio.set_event_loop(asyncio.new_event_loop())
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # --- user commands ---
    app.add_handler(CommandHandler("start", u.start))
    app.add_handler(CommandHandler("help", u.help_cmd))
    app.add_handler(CommandHandler("myorders", u.my_orders))

    # --- user callback buttons ---
    app.add_handler(CallbackQueryHandler(u.back_to_menu, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(u.help_cmd, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(u.browse, pattern="^browse:"))
    app.add_handler(CallbackQueryHandler(u.category_page, pattern="^cat:"))
    app.add_handler(CallbackQueryHandler(u.book_detail, pattern="^book:"))
    app.add_handler(CallbackQueryHandler(u.book_details, pattern="^details:"))
    app.add_handler(CallbackQueryHandler(u.buy, pattern="^buy:"))
    app.add_handler(CallbackQueryHandler(u.reminder_buy, pattern="^remindbuy:"))
    app.add_handler(CallbackQueryHandler(u.paid, pattern="^paid:"))
    app.add_handler(CallbackQueryHandler(u.my_orders, pattern="^myorders$"))

    # --- admin: add book conversation ---
    # IMPORTANT: this must be registered *before* the generic photo handler
    # below. Handlers in the same group are tried in registration order and
    # only the first match runs — so an admin's "cover photo" upload (part
    # of an active /addbook conversation) is claimed here first, and only
    # falls through to the buyer screenshot handler when no conversation is
    # active for that user.
    app.add_handler(a.addbook_conversation())

    # --- admin: edit book conversation ---
    # Same ordering reason as above — an admin's replacement cover photo or
    # file, sent mid-edit, must be claimed by this conversation before the
    # generic buyer screenshot handler ever sees it.
    app.add_handler(a.editbook_conversation())

    # --- payment screenshot (buyers) ---
    app.add_handler(MessageHandler(filters.PHOTO, u.receive_screenshot))

    # --- admin: catalog management ---
    app.add_handler(CommandHandler("listbooks", a.listbooks))
    app.add_handler(CommandHandler("stats", a.stats_cmd))
    app.add_handler(CallbackQueryHandler(a.admin_delete_book, pattern="^admdel:"))

    # --- admin: order approval ---
    app.add_handler(CallbackQueryHandler(a.admin_approve, pattern="^approve:"))
    app.add_handler(CallbackQueryHandler(a.admin_reject, pattern="^reject:"))

    # --- admin: manual reminder controls ---
    app.add_handler(a.reminder_conversation())

    logger.info("Bot starting (polling mode)...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()