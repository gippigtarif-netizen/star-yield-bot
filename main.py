import asyncio
import sqlite3
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

# Твой токен бота StarYield
TOKEN = "9187717570:AAFe52G8d-aVNkwFet3tr9yw9deRqFrDG9Q"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # Создаем таблицу пользователей, если ее еще нет
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
    # Проверяем, есть ли уже такой пользователь
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        # Если нет — добавляем с нулевым балансом
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, balance) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, 0)
        )
        conn.commit()
    conn.close()

# Утвержденный текст приветствия и правил
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
    "• ❌ <b>Нельзя отписываться от каналов в течение 3 дней</b>, иначе баланс будет аннулирован."
)

@dp.message(CommandStart())
async def start_handler(message: Message):
    # Сохраняем или проверяем пользователя в базе данных
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
    add_user(user_id, username, first_name)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Запустить StarYield", 
                    url="https://t.me/star_yield_bot" 
                )
            ]
        ]
    )
    
    await message.answer(
        text=WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def main():
    # Инициализируем базу данных при запуске
    init_db()
    print("🤖 Бот StarYield успешно запущен и база данных подключена!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
