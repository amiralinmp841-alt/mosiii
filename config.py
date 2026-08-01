import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "HarfChatBot")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-render-service.onrender.com")
PORT = int(os.getenv("PORT", "10000"))

# آیدی عددی گروه/کانال/سوپرگروهی که لاگ تغییرات دیتابیس به آن ارسال می‌شود
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "-1001234567890"))

# آیدی عددی ادمین
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

DB_FILE = os.getenv("DB_FILE", "db.json")
