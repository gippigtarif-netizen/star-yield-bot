import asyncio
import sqlite3
import os
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    LabeledPrice,
    PreCheckoutQuery,
)
from aiogram.filters import CommandStart

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://star-yield-bot.onrender.com")

# --- НАСТРОЙКИ КОЛЕСА X2 И КАССЫ ---
MIN_BET = 1
MAX_BET = 1000
MIN_TREASURY_RESERVE = 100  # Несгораемый запас звёзд в твоей кассе


def calculate_win_chance(bet_amount: int) -> float:
    """Плавный рост шанса от 1 до 1000 звёзд. Потолок строго < 1% (0.999%)."""
    if bet_amount < MIN_BET:
        return 0.0
    clamped_bet = min(bet_amount, MAX_BET)
    chance = 0.999 * ((clamped_bet / MAX_BET) ** 0.7)
    return round(min(chance, 0.999), 4)


# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            game_balance INTEGER DEFAULT 0,
            bonus_balance INTEGER DEFAULT 0
        )
    """)

    # Мягкая миграция, если база уже существовала со старой колонкой balance
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if "game_balance" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN game_balance INTEGER DEFAULT 0")
    if "bonus_balance" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN bonus_balance INTEGER DEFAULT 0")
        # Переносим старые накопленные звёзды на бонусный баланс
        cursor.execute("UPDATE users SET bonus_balance = COALESCE(balance, 0)")

    # Таблица состояния кассы бота
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treasury (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            amount INTEGER DEFAULT 0
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO treasury (id, amount) VALUES (1, 0)")

    conn.commit()
    conn.close()


def get_or_create_user(user_id: int, username: str = "", first_name: str = "") -> dict:
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT game_balance, bonus_balance FROM users WHERE user_id = ?", (user_id,)
    )
    row = cursor.fetchone()

    if not row:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, game_balance, bonus_balance) VALUES (?, ?, ?, 0, 0)",
            (user_id, username, first_name),
        )
        conn.commit()
        balances = {"game_balance": 0, "bonus_balance": 0}
    else:
        balances = {"game_balance": row[0] or 0, "bonus_balance": row[1] or 0}

    conn.close()
    return balances


def update_bonus_balance(user_id: int, amount: int, username: str = "", first_name: str = ""):
    get_or_create_user(user_id, username, first_name)
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET bonus_balance = MAX(0, bonus_balance + ?) WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()


def update_game_balance(user_id: int, amount: int, username: str = "", first_name: str = ""):
    get_or_create_user(user_id, username, first_name)
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET game_balance = MAX(0, game_balance + ?) WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()


# --- ПРИЁМ РЕАЛЬНЫХ TELEGRAM STARS (XTR) ---
@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payment = message.successful_payment
    stars_amount = payment.total_amount  # 1 XTR = 1 звезда
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""

    update_game_balance(user_id, stars_amount, username, first_name)
    await message.answer(
        f"✅ Оплата прошла успешно! На ваш <b>Игровой баланс</b> зачислено <b>{stars_amount} ⭐</b>.",
        parse_mode="HTML",
    )


WELCOME_TEXT = (
    "⭐️ <b>Добро пожаловать в StarYield!</b> ⭐️\n\n"
    "Вас приветствует StarYield! Выполняй лёгкие задания для накопления бонусных звёзд или испытай удачу в Колесе Фортуны X2.\n\n"
    "📌 <b>Два независимых баланса:</b>\n"
    "• 🎰 <b>Игровой баланс</b> — пополняется звёздами Telegram, используется в рулетке X2 и доступен для вывода.\n"
    "• 🎁 <b>Бонусный баланс</b> — копится за ежедневные задания и подписки, доступен для вывода от 500 ⭐.\n\n"
    "⚠️ <b>Правила:</b>\n"
    "• ❌ <b>Нельзя отписываться от каналов в течение 3 дней</b>, иначе бонусный баланс будет аннулирован.\n\n"
    "Нажимай кнопку ниже, чтобы открыть Mini App:"
)


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    get_or_create_user(user_id, username, first_name)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть StarYield App", web_app=WebAppInfo(url=RENDER_URL)
                )
            ]
        ]
    )
    await message.answer(text=WELCOME_TEXT, parse_mode="HTML", reply_markup=keyboard)


# --- API ДЛЯ МИНИ-ПРИЛОЖЕНИЯ ---
async def api_get_balance(request):
    try:
        user_id = int(request.rel_url.query.get("user_id", 0))
        username = request.rel_url.query.get("username", "")
        first_name = request.rel_url.query.get("first_name", "")

        if not user_id:
            return web.json_response({"error": "No user_id provided"}, status=400)

        balances = get_or_create_user(user_id, username, first_name)
        return web.json_response(balances)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


async def api_add_reward(request):
    """Начисляет награду исключительно на БОНУСНЫЙ баланс (задания)."""
    try:
        data = await request.json()
        user_id = int(data.get("user_id"))
        reward = int(data.get("reward", 0))
        username = data.get("username", "")
        first_name = data.get("first_name", "")

        # Защита от накрутки: за одно задание нельзя получить больше 50 звёзд
        if reward <= 0 or reward > 50:
            return web.json_response({"error": "Некорректная награда"}, status=400)

        update_bonus_balance(user_id, reward, username, first_name)
        balances = get_or_create_user(user_id)
        return web.json_response({"success": True, **balances})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


async def api_create_invoice(request):
    """Создаёт ссылку на оплату реальными Telegram Stars (XTR) для пополнения ИГРОВОГО баланса."""
    try:
        data = await request.json()
        amount = int(data.get("amount", 0))
        if amount < 1 or amount > 10000:
            return web.json_response({"error": "Введите сумму от 1 до 10000 ⭐"}, status=400)

        invoice_link = await bot.create_invoice_link(
            title=f"Пополнение на {amount} ⭐",
            description="Пополнение игрового баланса StarYield для Колеса Фортуны X2",
            payload=f"topup_{amount}",
            currency="XTR",
            prices=[LabeledPrice(label="Telegram Stars", amount=amount)],
        )
        return web.json_response({"invoice_link": invoice_link})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


async def api_spin_wheel(request):
    """Серверный расчёт вращения Колеса X2 с лимитом ставки 1..1000, шансом < 1% и проверкой кассы."""
    try:
        data = await request.json()
        user_id = int(data.get("user_id"))
        bet_amount = int(data.get("bet", 0))
        username = data.get("username", "")
        first_name = data.get("first_name", "")

        if bet_amount < MIN_BET or bet_amount > MAX_BET:
            return web.json_response(
                {"error": f"Ставка должна быть от {MIN_BET} до {MAX_BET} ⭐"}, status=400
            )

        get_or_create_user(user_id, username, first_name)

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()

        cursor.execute("SELECT game_balance, bonus_balance FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        game_balance, bonus_balance = row[0], row[1]

        if game_balance < bet_amount:
            conn.close()
            return web.json_response(
                {"error": "Недостаточно звёзд на Игровом балансе! Пополните его."}, status=400
            )

        cursor.execute("SELECT amount FROM treasury WHERE id = 1")
        current_treasury = cursor.fetchone()[0]

        # 1. Списываем ставку с игрового баланса и кладём в кассу
        new_game_balance = game_balance - bet_amount
        new_treasury = current_treasury + bet_amount
        potential_prize = bet_amount * 2
        win_chance = calculate_win_chance(bet_amount)

        # 2. Проверяем кассу и крутим рулетку (шанс строго < 1%)
        can_pay = (new_treasury - potential_prize) >= MIN_TREASURY_RESERVE
        is_win = can_pay and (random.uniform(0, 100) <= win_chance)

        prize = 0
        if is_win:
            prize = potential_prize
            new_game_balance += prize
            new_treasury -= prize

        cursor.execute(
            "UPDATE users SET game_balance = ? WHERE user_id = ?",
            (new_game_balance, user_id),
        )
        cursor.execute("UPDATE treasury SET amount = ? WHERE id = 1", (new_treasury,))
        conn.commit()
        conn.close()

        return web.json_response(
            {
                "success": True,
                "won": is_win,
                "prize": prize,
                "chance": win_chance,
                "game_balance": new_game_balance,
                "bonus_balance": bonus_balance,
            }
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


async def handle_index(request):
    return web.FileResponse("./index.html")


async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/get_balance", api_get_balance)
    app.router.add_post("/api/add_reward", api_add_reward)
    app.router.add_post("/api/create_invoice", api_create_invoice)
    app.router.add_post("/api/spin_wheel", api_spin_wheel)
    app.router.add_static("/", path=".", name="static")

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


async def main():
    init_db()
    print("🤖 Бот и Mini App StarYield успешно запущены!")
    await asyncio.gather(web_server(), dp.start_polling(bot))


if __name__ == "__main__":
    asyncio.run(main())
