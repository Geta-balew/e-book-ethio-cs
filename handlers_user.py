"""
Everything a regular customer interacts with:
  /start -> main menu -> browse catalog -> view book -> buy -> pay -> screenshot
"""

import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from html import escape as _esc

import db
from config import ADMIN_IDS, PAYMENT_INSTRUCTIONS, BOOKS_PER_PAGE, BOT_NAME, BOT_TAGLINE


AWAITING_SCREENSHOT = "awaiting_screenshot_for_book"


# ---------------------------------------------------------------------------
# MAIN MENU
# ---------------------------------------------------------------------------

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 መጽሐፍት ይመልከቱ", callback_data="browse:0")],
        [InlineKeyboardButton("🧾 ትዕዛዞቼ", callback_data="myorders")],
        [InlineKeyboardButton("ℹ️ እርዳታ", callback_data="help")],
    ])


# ---------------------------------------------------------------------------
# BOOK DISPLAY
# ---------------------------------------------------------------------------

def _book_caption(book):
    return (
        f"📖 <b>{_esc(book['title'])}</b>\n\n"
        f"{_esc(book['description'])}\n\n"
        f"💰 ዋጋ: {book['price']} {book['currency']}"
    )


def _book_kb(book, back_target=None, show_back=True):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "📚 ስለ መጽሐፉ በዝርዝር ይመልከቱ !",
            callback_data=f"details:{book['id']}"
        )
    ]])


def _details_caption(book):
    text = book["details"] or book["description"]

    return (
        f"📖 <b>{_esc(book['title'])}</b>\n\n"
        f"{_esc(text)}\n\n"
        f"💰 ዋጋ: {book['price']} {book['currency']}"
    )


def _details_kb(book, back_target=None, show_back=True):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ አሁን ልግዛ",
            callback_data=f"buy:{book['id']}"
        )
    ]])


# ---------------------------------------------------------------------------
# PAYMENT
# ---------------------------------------------------------------------------

def _pay_caption(book):
    copy_hint = "👉 ቁጥሮቹን በመንካት በቀላሉ ኮፒ ማድረግ ይችላሉ!"
    payment_text = re.sub(
        r"(?m)^\s*(ስም\s*:)",
        f"\n{copy_hint}\n\n\\1",
        PAYMENT_INSTRUCTIONS,
        count=1,
    )
    text = _esc(payment_text)

    # Make numeric payment/account values copy-friendly in Telegram.
    #
    # Example placeholders:
    # CBE: 0000000000
    # Bank of Abyssinia: 000000000
    # Phone: 000000000
    #
    # Only numbers appearing after a ":" at the end of a line
    # are wrapped in Telegram's <code> formatting.
    text = re.sub(
        r'(?m)(^.*?:\s*)(\d[\d\s-]*)$',
        r'\1<code>\2</code>',
        text
    )

    return text


def _pay_kb(book, cancel_target=None):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ ከፈልኩ",
                callback_data=f"paid:{book['id']}"
            )
        ],
    ])


# ---------------------------------------------------------------------------
# START
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    db.upsert_user(
        user.id,
        user.username,
        user.first_name
    )

    # Deep-link support: a link like t.me/<bot>?start=book_12 sends
    # "/start book_12" here, with "book_12" arriving as context.args[0].
    # This is how a Meta ad can land someone straight on one book's page
    # instead of the main menu.

    if context.args:
        payload = context.args[0]

        if payload.startswith("book_"):
            try:
                book_id = int(payload.split("_", 1)[1])
            except ValueError:
                book_id = None

            if book_id is not None:
                book = db.get_book(book_id)

                if book and book["active"]:
                    db.record_book_engagement(user.id, book_id)
                    # Land on the book's description page first — the
                    # payment page only appears after they tap Buy Now.
                    # No Back button here on purpose: someone who arrived
                    # via a book-specific ad link should only ever see
                    # this one book, never the rest of the catalog.
                    # The lock is remembered so it also holds if they tap
                    # Cancel from the payment page and land back here.

                    context.user_data["locked_book_id"] = book_id

                    caption = _book_caption(book)
                    kb = _book_kb(book, show_back=False)

                    if book["cover_file_id"]:
                        await update.message.reply_photo(
                            book["cover_file_id"],
                            caption=caption,
                            parse_mode="HTML",
                            reply_markup=kb
                        )
                    else:
                        await update.message.reply_text(
                            caption,
                            parse_mode="HTML",
                            reply_markup=kb
                        )

                    return

                await update.message.reply_text(
                    "ይህ መጽሐፍ አሁን አይገኝም — ይልቁንስ ሙሉውን መደብር እነሆ፦"
                )

                # falls through to the normal menu below

    context.user_data.pop("locked_book_id", None)

    text = (
        f"ሰላም እንኳን ወደ {BOT_NAME} በደህና መጡ።\n\n"
        f"{BOT_TAGLINE}"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_menu_kb()
    )


# ---------------------------------------------------------------------------
# HELP
# ---------------------------------------------------------------------------

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"ይህ የ{BOT_NAME} መጽሐፍት ቤተ-መጽሐፍት እንዴት እንደሚሰራ፦\n"
        "1. 'መጽሐፍት ይመልከቱ' የሚለውን ይጫኑ እና ርዕስ ይምረጡ።\n"
        "2. 'አሁን ልግዛ' የሚለውን ይጫኑ — የክፍያ መመሪያ ያገኛሉ።\n"
        "3. ይክፈሉ፣ ከዚያ 'ከፈልኩ' የሚለውን ይጫኑ እና እንደ ማረጋገጫ ስክሪንሾት ይላኩ።\n"
        "4. አድሚን ያረጋግጠዋል እና መጽሐፉ ራሱ በራሱ ይላክልዎታል።\n\n"
        "የግዢዎችዎን ሁኔታ ለማየት /myorders ይጠቀሙ።"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=main_menu_kb()
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=main_menu_kb()
        )


# ---------------------------------------------------------------------------
# CATEGORIES
# ---------------------------------------------------------------------------

def _category_kb(categories):
    rows = [
        [InlineKeyboardButton(c, callback_data=f"cat:{c}:0")]
        for c in categories
    ]

    rows.append([
        InlineKeyboardButton("⬅️ ተመለስ", callback_data="menu")
    ])

    return InlineKeyboardMarkup(rows)


async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    categories = db.list_categories()

    if not categories:
        await query.edit_message_text(
            "እስካሁን ምንም መጽሐፍት የሉም — በቅርቡ ይመልከቱ!",
            reply_markup=main_menu_kb()
        )
        return

    if len(categories) == 1:
        await _show_book_list(
            update,
            context,
            categories[0],
            0
        )
        return

    await query.edit_message_text(
        "ምድብ ይምረጡ፦",
        reply_markup=_category_kb(categories)
    )


async def category_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, category, page = query.data.split(":", 2)

    await _show_book_list(
        update,
        context,
        category,
        int(page)
    )


async def _show_book_list(update, context, category, page):
    query = update.callback_query

    offset = page * BOOKS_PER_PAGE

    books = db.list_books(
        category=category,
        offset=offset,
        limit=BOOKS_PER_PAGE
    )

    total = db.count_books(category=category)

    if not books:
        await query.edit_message_text(
            "በዚህ ምድብ ውስጥ ምንም መጽሐፍ አልተገኘም።",
            reply_markup=main_menu_kb()
        )
        return

    rows = [
        [
            InlineKeyboardButton(
                f"{b['title']} — {b['price']} {b['currency']}",
                callback_data=f"book:{b['id']}"
            )
        ]
        for b in books
    ]

    nav = []

    if page > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅️ ቀዳሚ",
                callback_data=f"cat:{category}:{page-1}"
            )
        )

    if offset + BOOKS_PER_PAGE < total:
        nav.append(
            InlineKeyboardButton(
                "ቀጣይ ➡️",
                callback_data=f"cat:{category}:{page+1}"
            )
        )

    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton(
            "⬅️ ተመለስ",
            callback_data="browse:0"
        )
    ])

    await query.edit_message_text(
        f"📂 {category}",
        reply_markup=InlineKeyboardMarkup(rows)
    )


# ---------------------------------------------------------------------------
# BOOK DETAIL
# ---------------------------------------------------------------------------

async def book_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    book_id = int(query.data.split(":")[1])

    book = db.get_book(book_id)

    if not book or not book["active"]:
        await query.edit_message_text(
            "ይህ መጽሐፍ ከአሁን በኋላ አይገኝም።",
            reply_markup=main_menu_kb()
        )
        return

    db.record_book_engagement(query.from_user.id, book_id)

    caption = _book_caption(book)

    # If this visitor arrived via that book's ad deep link, keep them
    # locked to it even when they loop back here via Cancel — no Back
    # button, no path to the rest of the catalog.

    locked = context.user_data.get("locked_book_id")

    kb = _book_kb(
        book,
        show_back=(locked != book_id)
    )

    if book["cover_file_id"]:
        await query.message.reply_photo(
            book["cover_file_id"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb
        )

        await query.message.delete()

    else:
        await query.edit_message_text(
            caption,
            parse_mode="HTML",
            reply_markup=kb
        )


# ---------------------------------------------------------------------------
# BOOK DETAILS
# ---------------------------------------------------------------------------

async def book_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    book_id = int(query.data.split(":")[1])

    book = db.get_book(book_id)

    if not book or not book["active"]:
        await query.edit_message_text(
            "ይህ መጽሐፍ ከአሁን በኋላ አይገኝም።",
            reply_markup=main_menu_kb()
        )
        return

    db.record_book_engagement(query.from_user.id, book_id)

    # Screenshots/preview images, sent as their own album before the text —
    # Telegram doesn't support inline buttons on a media group, so the
    # caption + Buy Now button always follow as a separate message.

    images = db.get_book_images(book_id)

    if images:
        media = [
            InputMediaPhoto(file_id)
            for file_id in images[:10]
        ]  # Telegram's cap per album

        try:
            await context.bot.send_media_group(
                query.message.chat_id,
                media=media
            )
        except Exception:
            pass  # don't let a bad/expired image block the rest of the page

    caption = _details_caption(book)

    # Same ad-visitor lock as the short landing page — no Back button, no
    # path to the rest of the catalog, if they arrived via that book's link.

    locked = context.user_data.get("locked_book_id")

    kb = _details_kb(
        book,
        show_back=(locked != book_id)
    )

    await query.message.reply_text(
        caption,
        parse_mode="HTML",
        reply_markup=kb
    )


# ---------------------------------------------------------------------------
# BUY / PAYMENT
# ---------------------------------------------------------------------------

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    book_id = int(query.data.split(":")[1])

    book = db.get_book(book_id)

    if not book or not book["active"]:
        await query.edit_message_text(
            "ይህ መጽሐፍ ከአሁን በኋላ አይገኝም።",
            reply_markup=main_menu_kb()
        )
        return

    db.record_book_engagement(query.from_user.id, book_id)

    text = _pay_caption(book)
    kb = _pay_kb(book)

    if book["cover_file_id"]:
        await query.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=kb
        )


async def reminder_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    book_id = int(query.data.split(":")[1])
    book = db.get_book(book_id)

    if not book or not book["active"]:
        await query.edit_message_text(
            "ይህ መጽሐፍ ከአሁን በኋላ አይገኝም።",
            reply_markup=main_menu_kb(),
        )
        return

    db.record_book_engagement(query.from_user.id, book_id)
    await query.message.reply_text(
        _pay_caption(book),
        parse_mode="HTML",
        reply_markup=_pay_kb(book),
    )


# ---------------------------------------------------------------------------
# PAYMENT CONFIRMATION
# ---------------------------------------------------------------------------

async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    book_id = int(query.data.split(":")[1])

    context.user_data[AWAITING_SCREENSHOT] = book_id

    await query.message.reply_text(
        "📸 እባክዎ የከፈሉበትን ማረጋገጫ ርሲት ስክሪንሾት አሁን ይላኩ። "
        "ከ 3 እስከ 5 ደቂቃ ውስጥ ክፍያዎ ተረጋግጦ መጽሃፉ እዚሁ ይደርስዎታል!።"
    )


# ---------------------------------------------------------------------------
# RECEIVE SCREENSHOT
# ---------------------------------------------------------------------------

async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    book_id = context.user_data.get(AWAITING_SCREENSHOT)

    if not book_id:
        return  # not in a "waiting for proof" state — ignore stray photos

    book = db.get_book(book_id)

    if not book:
        await update.message.reply_text(
            "ያ መጽሐፍ ከአሁን በኋላ የለም። እባክዎ እንደገና ይመልከቱ።"
        )

        context.user_data.pop(
            AWAITING_SCREENSHOT,
            None
        )

        return

    user = update.effective_user

    photo_file_id = update.message.photo[-1].file_id

    order_id = db.create_order(
        user.id,
        user.username,
        book_id,
        photo_file_id
    )

    context.user_data.pop(
        AWAITING_SCREENSHOT,
        None
    )

    await update.message.reply_text(
        "✅ ደርሶኛል! \n"
        "የክፍያ ማረጋገጫዎ ተልኳል እና በግምገማ ላይ ነው። \n"
        "እንደተፈቀደ ወዲያውኑ መጽሐፉን እዚህ ያገኛሉ።\n\n"
    )

    admin_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ Approve",
            callback_data=f"approve:{order_id}"
        ),
        InlineKeyboardButton(
            "❌ Reject",
            callback_data=f"reject:{order_id}"
        ),
    ]])

    caption = (
        f"🆕 Order #{order_id}\n"
        f"Book: {book['title']} ({book['price']} {book['currency']})\n"
        f"Buyer: {user.first_name} (@{user.username or 'no_username'}, id {user.id})"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                admin_id,
                photo_file_id,
                caption=caption,
                reply_markup=admin_kb
            )
        except Exception:
            pass  # admin may not have started the bot yet


# ---------------------------------------------------------------------------
# MY ORDERS
# ---------------------------------------------------------------------------

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query:
        await query.answer()

    user_id = update.effective_user.id

    orders = db.list_orders_for_user(user_id)

    if not orders:
        text = "እስካሁን ምንም ትዕዛዝ አላደረጉም።"

    else:
        icons = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌"
        }

        status_labels = {
            "pending": "በመጠባበቅ ላይ",
            "approved": "ጸድቋል",
            "rejected": "ተቀባይነት አላገኘም",
        }

        lines = [
            f"{icons.get(o['status'], '•')} #{o['id']} — {o['book_title']} "
            f"({status_labels.get(o['status'], o['status'])})"
            for o in orders
        ]

        text = "🧾 ትዕዛዞችዎ፦\n\n" + "\n".join(lines)

    if query:
        await query.edit_message_text(
            text,
            reply_markup=main_menu_kb()
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=main_menu_kb()
        )


# ---------------------------------------------------------------------------
# BACK TO MENU
# ---------------------------------------------------------------------------

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "ዋና ማውጫ፦",
        reply_markup=main_menu_kb()
    )