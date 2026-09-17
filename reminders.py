"""Manual ebook follow-up messages for users who showed interest but did not buy."""
from html import escape as _esc

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import db


async def send_followups(context: ContextTypes.DEFAULT_TYPE):
    sent = 0
    for candidate in db.list_manual_reminder_candidates():
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🛒 እሺ አሁን ልግዛ።",
                callback_data=f"remindbuy:{candidate['book_id']}",
            )
        ]])
        try:
            template = candidate["reminder_text"] or db.get_reminder_settings()["text"]
            text = template.replace(
                "{name}", _esc(candidate["first_name"] or "የተጠቃሚ ስም")
            ).replace("{title}", _esc(candidate["title"]))
            image_file_id = candidate["reminder_cover_file_id"]
            if image_file_id:
                await context.bot.send_photo(
                    chat_id=candidate["user_id"],
                    photo=image_file_id,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            else:
                await context.bot.send_message(
                    chat_id=candidate["user_id"],
                    text=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
        except Exception:
            continue
        db.mark_reminder_sent(candidate["user_id"], candidate["book_id"])
        sent += 1
    return sent
