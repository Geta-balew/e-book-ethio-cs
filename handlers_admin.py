"""
Admin-only tools:
  /addbook   - guided conversation to add a new e-book to the catalog
  /listbooks - view & delete existing books
  /stats     - quick sales overview
  Approve / Reject buttons on incoming orders
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, filters
from html import escape as _esc

import db
from config import ADMIN_IDS, DEFAULT_CURRENCY, BOT_NAME
from reminders import send_followups

TITLE, DESCRIPTION, PRICE, CATEGORY, FILE, COVER, DETAILS, DETAIL_IMAGES = range(8)


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            if update.message:
                await update.message.reply_text(f"This command is for {BOT_NAME} admins only.")
            return ConversationHandler.END
        return await func(update, context)
    return wrapper


# ---------- add book conversation ----------

@admin_only
async def addbook_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_book"] = {}
    await update.message.reply_text(
        "Let's add a new book. Send /cancel any time to stop.\n\n"
        "1️⃣ Send the *title*:", parse_mode="Markdown"
    )
    return TITLE


async def addbook_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_book"]["title"] = update.message.text.strip()
    await update.message.reply_text("2️⃣ Send a short *description*:", parse_mode="Markdown")
    return DESCRIPTION


async def addbook_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_book"]["description"] = update.message.text.strip()
    await update.message.reply_text(
        f"3️⃣ Send the *price* as a number (e.g. 9.99). Currency will be {DEFAULT_CURRENCY} "
        "unless you type it after, e.g. `9.99 EUR`.", parse_mode="Markdown"
    )
    return PRICE


async def addbook_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.strip().split()
    try:
        price = float(parts[0])
    except ValueError:
        await update.message.reply_text("That doesn't look like a number. Try again, e.g. 9.99")
        return PRICE
    currency = parts[1].upper() if len(parts) > 1 else DEFAULT_CURRENCY
    context.user_data["new_book"]["price"] = price
    context.user_data["new_book"]["currency"] = currency
    await update.message.reply_text(
        "4️⃣ Send a *category* for this book (e.g. Fiction, Business, Self-Help):",
        parse_mode="Markdown"
    )
    return CATEGORY


async def addbook_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_book"]["category"] = update.message.text.strip()
    await update.message.reply_text(
        "5️⃣ Now send the *e-book file itself* (PDF, EPUB, etc.) as a Telegram document.",
        parse_mode="Markdown"
    )
    return FILE


async def addbook_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("Please send the file as a document attachment.")
        return FILE
    context.user_data["new_book"]["file_id"] = update.message.document.file_id
    await update.message.reply_text(
        "6️⃣ Optional: send a *cover image* now, or type /skip to leave it without a cover.",
        parse_mode="Markdown"
    )
    return COVER


async def addbook_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["new_book"]["cover_file_id"] = update.message.photo[-1].file_id
    return await _prompt_details(update, context)


async def addbook_skip_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_book"]["cover_file_id"] = None
    return await _prompt_details(update, context)


async def _prompt_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "7️⃣ Optional: send a longer *detailed description* — this is what shows "
        "when a buyer taps \"ስለ መጽሐፉ በዝርዝር\" to read more before buying. "
        "Type /skip to leave it with just the short description.",
        parse_mode="Markdown"
    )
    return DETAILS


async def addbook_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_book"]["details"] = update.message.text.strip()
    return await _prompt_detail_images(update, context)


async def addbook_skip_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_book"]["details"] = None
    return await _prompt_detail_images(update, context)


async def _prompt_detail_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_book"]["detail_images"] = []
    await update.message.reply_text(
        "8️⃣ Optional: send up to 10 preview images (e.g. screenshots of the "
        "book's pages) one at a time — they'll show above the detailed "
        "description. Send /done when finished, or /skip to add none."
    )
    return DETAIL_IMAGES


async def addbook_detail_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text(
            "Please send an image, or type /done to finish, /skip to add none."
        )
        return DETAIL_IMAGES
    images = context.user_data["new_book"].setdefault("detail_images", [])
    if len(images) >= 10:
        await update.message.reply_text(
            "That's 10 images already — Telegram's limit per album. Type /done to finish."
        )
        return DETAIL_IMAGES
    images.append(update.message.photo[-1].file_id)
    await update.message.reply_text(
        f"Added image {len(images)}. Send another, or type /done to finish."
    )
    return DETAIL_IMAGES


async def addbook_finish_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _save_book(update, context)


async def _save_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    b = context.user_data["new_book"]
    book_id = db.add_book(
        title=b["title"], description=b["description"], price=b["price"],
        currency=b["currency"], category=b["category"], file_id=b["file_id"],
        cover_file_id=b.get("cover_file_id"), details=b.get("details"),
    )
    for i, file_id in enumerate(b.get("detail_images", [])):
        db.add_book_image(book_id, file_id, i)
    await update.message.reply_text(
        f"✅ Book added! #{book_id} — <b>{_esc(b['title'])}</b> ({b['price']} {b['currency']})",
        parse_mode="HTML"
    )
    context.user_data.pop("new_book", None)
    return ConversationHandler.END


async def addbook_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("new_book", None)
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def addbook_conversation():
    from telegram.ext import CommandHandler, MessageHandler, ConversationHandler as CH
    return CH(
        entry_points=[CommandHandler("addbook", addbook_start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbook_title)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbook_description)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbook_price)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbook_category)],
            FILE: [MessageHandler(filters.Document.ALL, addbook_file)],
            COVER: [
                MessageHandler(filters.PHOTO, addbook_cover),
                CommandHandler("skip", addbook_skip_cover),
            ],
            DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, addbook_details),
                CommandHandler("skip", addbook_skip_details),
            ],
            DETAIL_IMAGES: [
                MessageHandler(filters.PHOTO, addbook_detail_image),
                CommandHandler("done", addbook_finish_images),
                CommandHandler("skip", addbook_finish_images),
            ],
        },
        fallbacks=[CommandHandler("cancel", addbook_cancel)],
    )


# ---------- edit book conversation ----------

EDIT_CHOOSING, EDIT_VALUE, EDIT_IMAGES = range(100, 103)

FIELD_LABELS = {
    "title": "Title",
    "description": "Short description",
    "details": "Detailed description",
    "price": "Price",
    "currency": "Currency",
    "category": "Category",
    "file_id": "E-book file",
    "cover_file_id": "Cover image",
    "reminder_cover_file_id": "Reminder/ad cover",
    "reminder_text": "Reminder text",
    "detail_images": "Preview images",
}


def _edit_field_kb(book_id):
    rows, row = [], []
    for field, label in FIELD_LABELS.items():
        row.append(InlineKeyboardButton(label, callback_data=f"editfield:{book_id}:{field}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("✅ Done", callback_data=f"editdone:{book_id}")])
    return InlineKeyboardMarkup(rows)


def _edit_images_kb(book_id, images):
    rows = [
        [InlineKeyboardButton(
            f"🗑 Remove preview {index}",
            callback_data=f"editremoveimage:{book_id}:{image['id']}",
        )]
        for index, image in enumerate(images, 1)
    ]
    rows.append([
        InlineKeyboardButton("➕ Add preview image", callback_data=f"editaddimage:{book_id}"),
    ])
    rows.append([
        InlineKeyboardButton("✅ Done", callback_data=f"editimagesdone:{book_id}"),
    ])
    return InlineKeyboardMarkup(rows)


async def _show_edit_images(update: Update, context: ContextTypes.DEFAULT_TYPE, book_id: int):
    images = db.list_book_images(book_id)
    text = (
        f"Preview images for book #{book_id}: {len(images)}/10\n"
        "Remove an image individually, add another image, or tap Done."
    )
    reply_target = update.callback_query.message if update.callback_query else update.message
    await reply_target.reply_text(text, reply_markup=_edit_images_kb(book_id, images))


async def editbook_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Admins only.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    book_id = int(query.data.split(":")[1])
    book = db.get_book(book_id)
    if not book:
        await query.message.reply_text("That book no longer exists.")
        return ConversationHandler.END
    context.user_data["editing_book_id"] = book_id
    await query.message.reply_text(
        f"Editing #{book_id} — <b>{_esc(book['title'])}</b>\n"
        "Which field do you want to change? The book's ID and ad link stay "
        "the same no matter what you edit.",
        parse_mode="HTML",
        reply_markup=_edit_field_kb(book_id),
    )
    return EDIT_CHOOSING


async def editbook_choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Admins only.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    _, book_id, field = query.data.split(":")
    book_id = int(book_id)
    context.user_data["editing_book_id"] = book_id
    context.user_data["editing_field"] = field
    label = FIELD_LABELS.get(field, field)

    if field == "detail_images":
        await _show_edit_images(update, context, book_id)
        return EDIT_IMAGES
    elif field == "file_id":
        await query.message.reply_text(f"Send the new *{label}* as a document attachment.",
                                        parse_mode="Markdown")
    elif field in {"cover_file_id", "reminder_cover_file_id"}:
        await query.message.reply_text(
            f"Send the new *{label}* as a photo, or type /remove to clear it. "
            "Reminder ads fall back to the regular cover when no ad cover is set.",
            parse_mode="Markdown",
        )
    elif field == "price":
        await query.message.reply_text(
            "Send the new *price* as a number (e.g. 9.99). Add a currency after it "
            "to change that too, e.g. `9.99 EUR`.", parse_mode="Markdown"
        )
    elif field == "reminder_text":
        await query.message.reply_text(
            "Send this book's reminder text. Use {name} for the user's name and "
            "{title} for the book title. Formatting: <b>bold</b>, <i>italic</i>, "
            "<u>underline</u>, or <code>code</code>."
        )
    else:
        await query.message.reply_text(f"Send the new *{label}*:", parse_mode="Markdown")
    return EDIT_VALUE


async def editbook_image_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Admins only.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    action, book_id, image_id = query.data.split(":")
    book_id = int(book_id)
    if action == "editremoveimage":
        db.remove_book_image(book_id, int(image_id))
    await _show_edit_images(update, context, book_id)
    return EDIT_IMAGES


async def editbook_add_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Admins only.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    book_id = int(query.data.split(":")[1])
    if len(db.list_book_images(book_id)) >= 10:
        await query.message.reply_text("There are already 10 preview images. Remove one before adding another.")
        return EDIT_IMAGES
    context.user_data["editing_book_id"] = book_id
    await query.message.reply_text("Send the new preview image, or tap Done when finished.")
    return EDIT_IMAGES


async def editbook_images_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    book_id = int(query.data.split(":")[1])
    await query.message.reply_text(
        "✅ Preview images updated. Edit another field, or tap Done:",
        reply_markup=_edit_field_kb(book_id),
    )
    return EDIT_CHOOSING


async def editbook_remove_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    book_id = context.user_data.get("editing_book_id")
    if not book_id or context.user_data.get("editing_field") not in {
        "cover_file_id", "reminder_cover_file_id"
    }:
        await update.message.reply_text("Choose the cover image field before using /remove.")
        return EDIT_VALUE
    field = context.user_data["editing_field"]
    db.update_book_field(book_id, field, None)
    context.user_data.pop("editing_field", None)
    await update.message.reply_text(
        "✅ Cover removed. Edit another field, or tap Done:",
        reply_markup=_edit_field_kb(book_id),
    )
    return EDIT_CHOOSING


async def editbook_receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    book_id = context.user_data.get("editing_book_id")
    if not book_id:
        return ConversationHandler.END
    if not update.message.photo:
        await update.message.reply_text("Please send an image, or type /done to finish.")
        return EDIT_IMAGES
    count = len(db.list_book_images(book_id))
    if count >= 10:
        await update.message.reply_text(
            "That's 10 images already — Telegram's limit per album. Type /done to finish."
        )
        return EDIT_IMAGES
    db.add_book_image(book_id, update.message.photo[-1].file_id, count)
    count += 1
    context.user_data["editing_image_count"] = count
    await update.message.reply_text(f"Added image {count}. Send another, or type /done to finish.")
    return EDIT_IMAGES


async def editbook_finish_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    book_id = context.user_data.get("editing_book_id")
    context.user_data.pop("editing_field", None)
    context.user_data.pop("editing_image_count", None)
    await update.message.reply_text(
        "✅ Preview images updated. Edit another field, or tap Done:",
        reply_markup=_edit_field_kb(book_id),
    )
    return EDIT_CHOOSING


async def editbook_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    book_id = context.user_data.get("editing_book_id")
    field = context.user_data.get("editing_field")
    if not book_id or not field:
        return ConversationHandler.END

    if field == "file_id":
        if not update.message.document:
            await update.message.reply_text("Please send the file as a document attachment.")
            return EDIT_VALUE
        db.update_book_field(book_id, "file_id", update.message.document.file_id)

    elif field in {"cover_file_id", "reminder_cover_file_id"}:
        if not update.message.photo:
            await update.message.reply_text("Please send a photo.")
            return EDIT_VALUE
        db.update_book_field(book_id, field, update.message.photo[-1].file_id)

    elif field == "price":
        if not update.message.text:
            await update.message.reply_text("Please send the new price as text, e.g. 9.99")
            return EDIT_VALUE
        parts = update.message.text.strip().split()
        try:
            price = float(parts[0])
        except ValueError:
            await update.message.reply_text("That doesn't look like a number. Try again, e.g. 9.99")
            return EDIT_VALUE
        db.update_book_field(book_id, "price", price)
        if len(parts) > 1:
            db.update_book_field(book_id, "currency", parts[1].upper())

    else:  # title, description, category — plain text
        if not update.message.text:
            await update.message.reply_text("Please send this as text.")
            return EDIT_VALUE
        db.update_book_field(book_id, field, update.message.text.strip())

    context.user_data.pop("editing_field", None)
    await update.message.reply_text(
        "✅ Updated. Edit another field, or tap Done:",
        reply_markup=_edit_field_kb(book_id),
    )
    return EDIT_CHOOSING


async def editbook_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    book_id = query.data.split(":")[1]
    await query.message.reply_text(f"✅ Done editing book #{book_id}.")
    context.user_data.pop("editing_book_id", None)
    context.user_data.pop("editing_field", None)
    return ConversationHandler.END


async def editbook_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("editing_book_id", None)
    context.user_data.pop("editing_field", None)
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def editbook_conversation():
    from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, ConversationHandler as CH
    return CH(
        entry_points=[CallbackQueryHandler(editbook_entry, pattern="^admedit:")],
        states={
            EDIT_CHOOSING: [
                CallbackQueryHandler(editbook_choose_field, pattern="^editfield:"),
                CallbackQueryHandler(editbook_done, pattern="^editdone:"),
            ],
            EDIT_VALUE: [
                CommandHandler("remove", editbook_remove_cover),
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.Document.ALL,
                    editbook_receive,
                ),
            ],
            EDIT_IMAGES: [
                CallbackQueryHandler(editbook_image_action, pattern="^editremoveimage:"),
                CallbackQueryHandler(editbook_add_image, pattern="^editaddimage:"),
                CallbackQueryHandler(editbook_images_done, pattern="^editimagesdone:"),
                MessageHandler(filters.PHOTO, editbook_receive_image),
                CommandHandler("done", editbook_finish_images),
            ],
        },
        fallbacks=[CommandHandler("cancel", editbook_cancel)],
    )


# ---------- list / remove books ----------

@admin_only
async def listbooks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    books = db.list_books(limit=100)
    if not books:
        await update.message.reply_text("No books in the catalog yet. Use /addbook to add one.")
        return
    for b in books:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✏️ Edit", callback_data=f"admedit:{b['id']}"),
            InlineKeyboardButton("🗑 Remove from library", callback_data=f"admdel:{b['id']}"),
        ], [
            InlineKeyboardButton("📣 Reminder controls", callback_data="reminder:open"),
        ]])
        bot_username = context.bot.username
        text = (
            f"#{b['id']} <b>{_esc(b['title'])}</b> — {b['price']} {b['currency']} "
            f"[{_esc(b['category'])}]\n"
            f"🔗 https://t.me/{bot_username}?start=book_{b['id']}"
        )
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def admin_delete_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Admins only.", show_alert=True)
        return
    await query.answer()
    book_id = int(query.data.split(":")[1])
    # Deactivate rather than hard-delete: a book can already have orders
    # tied to it, and permanently deleting it would break that order
    # history (and raise a foreign-key error). Deactivating hides it from
    # the library and from /listbooks while keeping past orders intact.
    db.deactivate_book(book_id)
    await query.edit_message_text(f"🗑 Book #{book_id} removed from the library.")


# ---------- approve / reject orders ----------

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Admins only.", show_alert=True)
        return
    await query.answer()
    order_id = int(query.data.split(":")[1])
    order = db.get_order(order_id)
    if not order or order["status"] != "pending":
        await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n(Already handled)")
        return

    book = db.get_book(order["book_id"])
    db.set_order_status(order_id, "approved")

    try:
        await context.bot.send_document(
            order["user_id"], book["file_id"],
            caption=f"🎉 ስላደረጉት ግዥ እናመሰግናለን ይኸው — <b>{_esc(book['title'])}</b>።",
            parse_mode="HTML",
        )
    except Exception:
        await context.bot.send_message(
            order["user_id"],
            "Your order was approved but we couldn't deliver the file automatically — "
            "an admin will follow up.",
        )

    await query.edit_message_caption(
        caption=(query.message.caption or "") + f"\n\n✅ Approved by {query.from_user.first_name}"
    )


async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Admins only.", show_alert=True)
        return
    await query.answer()
    order_id = int(query.data.split(":")[1])
    order = db.get_order(order_id)
    if not order or order["status"] != "pending":
        await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n(Already handled)")
        return

    db.set_order_status(order_id, "rejected")
    try:
        await context.bot.send_message(
            order["user_id"],
            "❌ Your payment proof was not approved. If you believe this is a mistake, "
            "please contact support.",
        )
    except Exception:
        pass

    await query.edit_message_caption(
        caption=(query.message.caption or "") + f"\n\n❌ Rejected by {query.from_user.first_name}"
    )


@admin_only
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = db.stats()
    text = (
        "📊 *e-book ethio cs Stats*\n\n"
        f"Active books: {s['total_books']}\n"
        f"Total orders: {s['total_orders']}\n"
        f"Pending: {s['pending']}\n"
        f"Approved: {s['approved']}\n"
        f"Revenue (approved orders): {s['revenue']:.2f}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------- manual reminders ----------

REMINDER_PANEL, REMINDER_TEXT, REMINDER_IMAGE = range(200, 203)


def _reminder_panel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📣 Spread reminder now", callback_data="reminder:spread")],
    ])


@admin_only
async def reminder_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    settings = db.get_reminder_settings()
    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text(
        "📣 Reminder controls\n\n"
        "Each book has its own reminder text and image. Edit them from the book's "
        "Edit button, then spread reminders manually to eligible engaged users.\n\n"
        "Use {name} and {title} in reminder text.\n"
        "Formatting: <b>bold</b>, <i>italic</i>, <u>underline</u>, <code>code</code>.",
        parse_mode="HTML",
        reply_markup=_reminder_panel_kb(),
    )
    return REMINDER_PANEL


async def reminder_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Admins only.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    action = query.data.split(":")[1]
    if action == "spread":
        sent = await send_followups(context)
        await query.edit_message_text(f"✅ Reminder sent to {sent} eligible engaged users.")
        return ConversationHandler.END
    if action == "clear":
        db.update_reminder_setting("image_file_id", None)
        await query.edit_message_text("✅ Reminder image cleared. The book cover will be used when available.")
        return ConversationHandler.END
    if action == "text":
        await query.message.reply_text(
            "Send the new reminder text. You can use {name} for the user's name and {title} for the book title."
        )
        return REMINDER_TEXT
    await query.message.reply_text("Send the new reminder image as a photo.")
    return REMINDER_IMAGE


async def reminder_receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        await update.message.reply_text("Please send the reminder text as a message.")
        return REMINDER_TEXT
    db.update_reminder_setting("text", update.message.text.strip())
    await update.message.reply_text("✅ Reminder text updated. Use /reminder to review or spread it.")
    return ConversationHandler.END


async def reminder_receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Please send the reminder image as a photo.")
        return REMINDER_IMAGE
    db.update_reminder_setting("image_file_id", update.message.photo[-1].file_id)
    await update.message.reply_text("✅ Reminder image updated. Use /reminder to review or spread it.")
    return ConversationHandler.END


def reminder_conversation():
    from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, ConversationHandler as CH
    return CH(
        entry_points=[
            CommandHandler("reminder", reminder_panel),
            CallbackQueryHandler(reminder_panel, pattern="^reminder:open$"),
        ],
        states={
            REMINDER_PANEL: [CallbackQueryHandler(reminder_action, pattern="^reminder:")],
            REMINDER_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminder_receive_text)],
            REMINDER_IMAGE: [MessageHandler(filters.PHOTO, reminder_receive_image)],
        },
        fallbacks=[CommandHandler("cancel", editbook_cancel)],
        allow_reentry=True,
        per_user=True,
    )