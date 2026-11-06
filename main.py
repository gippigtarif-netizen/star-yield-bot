import asyncio
import sqlite3
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://star-yield-bot.onrender.com")

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, balance) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, 0)
        )
        conn.commit()
    conn.close()

def get_user_balance(user_id: int) -> int:
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def update_user_balance(user_id: int, amount: int):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

WELCOME_TEXT = (
    "⭐️ <b>Добро пожаловать в StarYield!</b> ⭐️\n\n"
    "Вас приветствует StarYield! В этом боте можно бесплатно получать реальные тг-звёзды за выполнение лёгких заданий. "
    "Зарабатывай честные награды за подписки и активность в сервисе.\n\n"
    "📌 <b>Как это работает:</b>\n"
    "• Выполняй простые задания и подписывайся на каналы.\n"
    "• Следи за своими накоплениями в профиле.\n"
    "• Выводи заработанные звёзды и развивайся вместе с проектом.\n\n"
    "⚠️ <b>Дисклеймер и правила:</b>\n"
    "• 🔞 В рамках партнерских заданий может рекламироваться контент для взрослых (18+).\n"
    "• ❌ <b>Нельзя отписываться от каналов в течение 3 дней</b>, иначе баланс будет аннулирован.\n\n"
    "Нажимай кнопку ниже, чтобы открыть Mini App:"
)

@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    add_user(user_id, username, first_name)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть StarYield App", 
                    web_app=WebAppInfo(url=RENDER_URL)
                )
            ]
        ]
    )
    await message.answer(
        text=WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=keyboard
    )

# --- API ДЛЯ МИНИ-ПРИЛОЖЕНИЯ ---
async def api_get_balance(request):
    user_id = request.rel_url.query.get("user_id")
    if not user_id:
        return web.json_response({"error": "No user_id provided"}, status=400)
    
    balance = get_user_balance(int(user_id))
    return web.json_response({"balance": balance})

async def api_add_reward(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id"))
        reward = int(data.get("reward", 0))
        
        update_user_balance(user_id, reward)
        new_balance = get_user_balance(user_id)
        return web.json_response({"success": True, "balance": new_balance})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def handle_index(request):
    return web.FileResponse('./index.html')

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/get_balance", api_get_balance)
    app.router.add_post("/api/add_reward", api_add_reward)
    app.router.add_static("/", path=".", name="static")
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    init_db()
    print("🤖 Бот и Mini App StarYield успешно запущены с поддержкой БД!")
    await asyncio.gather(
        web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
