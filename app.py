import os
import json
import secrets
import random
import logging
from typing import Optional, Dict, Any

from flask import Flask, request, jsonify
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, BOT_USERNAME, WEBHOOK_URL, PORT, LOG_CHAT_ID, ADMIN_ID, DB_FILE


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# -----------------------------
# DB Helpers
# -----------------------------
def load_db() -> Dict[str, Any]:
    if not os.path.exists(DB_FILE):
        default_db = {
            "users": {},
            "tokens": {},
            "messages": {},
            "meta": {
                "last_message_id": 0
            }
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(default_db, f, ensure_ascii=False, indent=2)
        return default_db

    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db: Dict[str, Any]) -> None:
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


async def save_db_and_notify(app: Application, db: Dict[str, Any], reason: str = "database updated") -> None:
    save_db(db)
    try:
        with open(DB_FILE, "rb") as f:
            await app.bot.send_document(
                chat_id=LOG_CHAT_ID,
                document=f,
                caption=f"📦 DB Updated\nReason: {reason}"
            )
    except Exception as e:
        logger.exception("Failed to send DB file to log group: %s", e)


def get_user_link(token: str) -> str:
    return f"https://t.me/{BOT_USERNAME}?start={token}"


def ensure_user(db: Dict[str, Any], user) -> Dict[str, Any]:
    user_id = str(user.id)

    if user_id not in db["users"]:
        token = secrets.token_hex(6)  # 12 chars hex
        while token in db["tokens"]:
            token = secrets.token_hex(6)

        username_display = user.username if user.username else (user.first_name or "کاربر")

        db["users"][user_id] = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "display_name": username_display,
            "token": token,
            "joined_at": None
        }
        db["tokens"][token] = user.id
    else:
        db["users"][user_id]["username"] = user.username
        db["users"][user_id]["first_name"] = user.first_name
        if user.username:
            db["users"][user_id]["display_name"] = user.username
        elif user.first_name:
            db["users"][user_id]["display_name"] = user.first_name

    return db["users"][user_id]


def generate_sender_code() -> str:
    return str(random.randint(1000000, 9999999))


def next_message_id(db: Dict[str, Any]) -> int:
    db["meta"]["last_message_id"] += 1
    return db["meta"]["last_message_id"]


# -----------------------------
# Bot Texts / Keyboards
# -----------------------------
def main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🔗 لینک ناشناس من")]],
        resize_keyboard=True
    )


def reaction_reply_keyboard(message_id: int, sender_code: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("پاسخ", callback_data=f"reply:{message_id}:{sender_code}"),
            InlineKeyboardButton("ری‌اکشن", callback_data=f"react:{message_id}:{sender_code}")
        ]
    ])


# -----------------------------
# Handlers
# -----------------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user = update.effective_user
    ensured = ensure_user(db, user)

    if not db["users"][str(user.id)].get("joined_at"):
        db["users"][str(user.id)]["joined_at"] = str(update.effective_message.date)

    await save_db_and_notify(context.application, db, reason=f"user_start:{user.id}")

    # اگر /start با token باشد
    if context.args:
        token = context.args[0].strip()
        target_user_id = db["tokens"].get(token)

        if target_user_id:
            target_data = db["users"].get(str(target_user_id))
            target_name = target_data.get("display_name", "کاربر")

            context.user_data["target_token"] = token
            context.user_data["target_user_id"] = int(target_user_id)
            context.user_data["awaiting_anonymous_message"] = True

            if int(target_user_id) == user.id:
                text = (
                    "Harf Chat:\n"
                    "داری به خودت پیام میدی؟😁\n"
                    "اشکال نداره اما امیدوارم از تنهایی نباشه:)\n\n"
                    f"در حال ارسال پیام ناشناس به « {target_name} » هستی:)\n\n"
                    "می‌تونی هر حرف یا انتقادی که تو دلت هست رو بگی چون پیامت به صورت کاملا ناشناس ارسال می‌شه!"
                )
            else:
                text = (
                    "Harf Chat:\n"
                    "در حال یافتن کاربر...\n\n"
                    f"در حال ارسال پیام ناشناس به « {target_name} » هستی:)\n\n"
                    "می‌تونی هر حرف یا انتقادی که تو دلت هست رو بگی چون پیامت به صورت کاملا ناشناس ارسال می‌شه!"
                )

            await update.message.reply_text(text)
            return

    text = (
        "به ربات پیام ناشناس حرف خوش اومدی🤗\n"
        "برای شروع از دکمه ها استفاده کن🔥"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard())


async def my_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user = update.effective_user
    ensured = ensure_user(db, user)

    await save_db_and_notify(context.application, db, reason=f"my_link:{user.id}")

    link = get_user_link(ensured["token"])
    display_name = ensured.get("display_name", "کاربر")

    text = (
        f"سلام {display_name} هستم ✋\n"
        "از طریق لینک زیر می‌تونی هرچی خواستی ناشناس برام بفرستی 🤫\n\n"
        f"{link}"
    )
    await update.message.reply_text(text, disable_web_page_preview=True)


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user = update.effective_user
    ensure_user(db, user)

    text = update.message.text.strip()

    if text == "🔗 لینک ناشناس من":
        await my_link_handler(update, context)
        return

    # اگر در حالت ارسال ناشناس هست
    if context.user_data.get("awaiting_anonymous_message") and context.user_data.get("target_user_id"):
        sender_id = user.id
        receiver_id = context.user_data["target_user_id"]

        sender_data = db["users"].get(str(sender_id))
        receiver_data = db["users"].get(str(receiver_id))

        if not receiver_data:
            await update.message.reply_text("کاربر مقصد پیدا نشد.")
            return

        sender_code = generate_sender_code()
        msg_id = next_message_id(db)

        db["messages"][str(msg_id)] = {
            "id": msg_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "sender_code": sender_code,
            "text": text,
            "reply_to": None,
            "created_at": str(update.effective_message.date)
        }

        await save_db_and_notify(context.application, db, reason=f"new_message:{msg_id}")

        receiver_text = (
            "Harf Chat:\n"
            f"کاربری با کد رمز {sender_code} پیام زیر رو فرستاد\n\n"
            "‌\n"
            f"{text}"
        )

        try:
            await context.application.bot.send_message(
                chat_id=receiver_id,
                text=receiver_text,
                reply_markup=reaction_reply_keyboard(msg_id, sender_code)
            )
        except Exception as e:
            logger.exception("Failed to send anonymous message: %s", e)
            await update.message.reply_text("ارسال پیام به گیرنده ممکن نشد.")
            return

        sender_link = get_user_link(sender_data["token"])
        sender_text = (
            "پیامت با موفقیت ارسال شد✅\n\n"
            "این لینک ناشناس خودته اگه می‌خوای برای دوستات بفرست تا بهت پیام بدن❤️👇🏻 \n"
            f"{sender_link}"
        )
        await update.message.reply_text(sender_text, disable_web_page_preview=True)

        context.user_data["awaiting_anonymous_message"] = False
        context.user_data["target_user_id"] = None
        context.user_data["target_token"] = None
        return

    await update.message.reply_text(
        "برای شروع از دکمه زیر استفاده کن 👇",
        reply_markup=main_keyboard()
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    db = load_db()
    data = query.data

    if data.startswith("reply:"):
        parts = data.split(":")
        if len(parts) != 3:
            await query.message.reply_text("داده پاسخ نامعتبر است.")
            return

        msg_id = parts[1]
        sender_code = parts[2]

        msg_data = db["messages"].get(msg_id)
        if not msg_data:
            await query.message.reply_text("پیام اصلی پیدا نشد.")
            return

        original_sender_id = msg_data["sender_id"]
        context.user_data["awaiting_reply"] = True
        context.user_data["reply_target_user_id"] = original_sender_id
        context.user_data["reply_to_message_id"] = int(msg_id)

        await query.message.reply_text(
            f"پاسخ خودت به کاربر با کد {sender_code} رو بفرست."
        )
        return

    if data.startswith("react:"):
        parts = data.split(":")
        if len(parts) != 3:
            await query.message.reply_text("داده ری‌اکشن نامعتبر است.")
            return

        msg_id = parts[1]
        sender_code = parts[2]

        react_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("❤️", callback_data=f"sendreact:{msg_id}:❤️"),
                InlineKeyboardButton("🔥", callback_data=f"sendreact:{msg_id}:🔥"),
                InlineKeyboardButton("😍", callback_data=f"sendreact:{msg_id}:😍"),
            ],
            [
                InlineKeyboardButton("😂", callback_data=f"sendreact:{msg_id}:😂"),
                InlineKeyboardButton("😢", callback_data=f"sendreact:{msg_id}:😢"),
                InlineKeyboardButton("👏", callback_data=f"sendreact:{msg_id}:👏"),
            ]
        ])
        await query.message.reply_text("یک ری‌اکشن انتخاب کن:", reply_markup=react_kb)
        return

    if data.startswith("sendreact:"):
        parts = data.split(":")
        if len(parts) != 3:
            await query.message.reply_text("داده ری‌اکشن نامعتبر است.")
            return

        msg_id = parts[1]
        emoji = parts[2]

        msg_data = db["messages"].get(msg_id)
        if not msg_data:
            await query.message.reply_text("پیام پیدا نشد.")
            return

        original_sender_id = msg_data["sender_id"]
        receiver_id = msg_data["receiver_id"]

        try:
            await context.application.bot.send_message(
                chat_id=original_sender_id,
                text=f"واکنش جدید به پیام ناشناس تو: {emoji}"
            )
            await query.message.reply_text("ری‌اکشن ارسال شد✅")
        except Exception as e:
            logger.exception("Failed to send reaction: %s", e)
            await query.message.reply_text("ارسال ری‌اکشن ناموفق بود.")
        return


async def reply_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_reply"):
        return

    db = load_db()
    sender_user = update.effective_user
    target_user_id = context.user_data.get("reply_target_user_id")
    reply_to_message_id = context.user_data.get("reply_to_message_id")
    text = update.message.text.strip()

    if not target_user_id:
        await update.message.reply_text("کاربر مقصد برای پاسخ پیدا نشد.")
        context.user_data["awaiting_reply"] = False
        return

    msg_id = next_message_id(db)
    sender_code = generate_sender_code()

    db["messages"][str(msg_id)] = {
        "id": msg_id,
        "sender_id": sender_user.id,
        "receiver_id": target_user_id,
        "sender_code": sender_code,
        "text": text,
        "reply_to": reply_to_message_id,
        "created_at": str(update.effective_message.date)
    }

    await save_db_and_notify(context.application, db, reason=f"reply_message:{msg_id}")

    try:
        await context.application.bot.send_message(
            chat_id=target_user_id,
            text=(
                "Harf Chat:\n"
                "پاسخ جدید برات ارسال شده:\n\n"
                f"{text}"
            )
        )
        await update.message.reply_text("پاسخ ارسال شد✅")
    except Exception as e:
        logger.exception("Failed to send reply: %s", e)
        await update.message.reply_text("ارسال پاسخ انجام نشد.")

    context.user_data["awaiting_reply"] = False
    context.user_data["reply_target_user_id"] = None
    context.user_data["reply_to_message_id"] = None


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id != ADMIN_ID:
        return

    document = update.message.document
    if not document:
        return

    if not document.file_name.lower().endswith(".json"):
        await update.message.reply_text("فقط فایل JSON مجاز است.")
        return

    file = await document.get_file()
    temp_path = "uploaded_db.json"
    await file.download_to_drive(temp_path)

    try:
        with open(temp_path, "r", encoding="utf-8") as f:
            new_db = json.load(f)

        # اعتبارسنجی ساده
        if not all(k in new_db for k in ["users", "tokens", "messages", "meta"]):
            await update.message.reply_text("ساختار فایل دیتابیس معتبر نیست.")
            return

        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(new_db, f, ensure_ascii=False, indent=2)

        await update.message.reply_text("دیتابیس با موفقیت جایگزین شد✅")

        try:
            with open(DB_FILE, "rb") as f:
                await context.application.bot.send_document(
                    chat_id=LOG_CHAT_ID,
                    document=f,
                    caption="📥 Database replaced by admin"
                )
        except Exception as e:
            logger.exception("Failed to notify log group after db replace: %s", e)

    except Exception as e:
        logger.exception("Invalid JSON upload: %s", e)
        await update.message.reply_text("فایل JSON نامعتبر است.")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# -----------------------------
# Flask + Telegram App
# -----------------------------
flask_app = Flask(__name__)
telegram_app = Application.builder().token(BOT_TOKEN).build()


def register_handlers(app_: Application):
    app_.add_handler(CommandHandler("start", start_handler))
    app_.add_handler(CallbackQueryHandler(callback_handler))
    app_.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app_.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_text_handler), group=0)
    app_.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler), group=1)


register_handlers(telegram_app)


@flask_app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "service": "HarfChatBot"}), 200


@flask_app.route("/set_webhook", methods=["GET"])
async def set_webhook():
    webhook_url = f"{WEBHOOK_URL}/webhook"
    await telegram_app.bot.set_webhook(url=webhook_url)
    return jsonify({"ok": True, "webhook": webhook_url})


@flask_app.route("/webhook", methods=["POST"])
async def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return "OK", 200
    except Exception as e:
        logger.exception("Webhook error: %s", e)
        return "ERROR", 500


async def init_telegram():
    await telegram_app.initialize()
    await telegram_app.start()


import asyncio
loop = asyncio.get_event_loop()
loop.run_until_complete(init_telegram())


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)
