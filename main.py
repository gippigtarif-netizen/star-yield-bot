import os
import random
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

BOT_TOKEN = os.getenv("BOT_TOKEN", "9187717570:AAFe52G8d-aVNkwFet3tr9yw9deRqFrDG9Q")
WEBAPP_URL = "https://star-yield-bot.onrender.com"
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = 7449913629

GIFT_EMOJI_NAMES = {
    "🎁": "Подарок",
    "💐": "Букет",
    "🧸": "Мишка",
    "❤️": "Сердечко",
    "💖": "Сердечко",
    "💝": "Сердечко с лентой",
    "🌹": "Роза",
    "🎂": "Торт",
    "🍾": "Шампанское",
    "🏆": "Кубок",
    "💍": "Кольцо",
    "💎": "Алмаз",
    "🚀": "Ракета",
}


def format_gift_name(gift: dict, index: int) -> str:
    emoji = (gift.get("sticker") or {}).get("emoji") or "🎁"
    if emoji in GIFT_EMOJI_NAMES:
        return f"{emoji} {GIFT_EMOJI_NAMES[emoji]}"
    return f"{emoji} Подарок #{index + 1}"


def get_db_connection():
    if DATABASE_URL:
        url = urlparse(DATABASE_URL)
        return psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port,
        )
    import sqlite3
    return sqlite3.connect("users.db")


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    id_type = "BIGINT" if DATABASE_URL else "INTEGER"
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS users (
            user_id {id_type} PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            game_balance INTEGER DEFAULT 0,
            bonus_balance INTEGER DEFAULT 0
        )
        """
    )
    if DATABASE_URL:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                telegram_payment_charge_id TEXT UNIQUE NOT NULL,
                total_amount INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'XTR',
                refunded BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            ALTER TABLE payments
            ADD COLUMN IF NOT EXISTS refunded BOOLEAN NOT NULL DEFAULT FALSE
            """
        )
    conn.commit()
    cursor.close()
    conn.close()


init_db()


def save_payment(user_id: int, charge_id: str, total_amount: int, currency: str = "XTR"):
    if not DATABASE_URL or not charge_id:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO payments (user_id, telegram_payment_charge_id, total_amount, currency, refunded)
        VALUES (%s, %s, %s, %s, FALSE)
        ON CONFLICT (telegram_payment_charge_id) DO NOTHING
        """,
        (user_id, charge_id, total_amount, currency),
    )
    conn.commit()
    cursor.close()
    conn.close()


def get_or_create_user(user_id: int, username: str = "", first_name: str = ""):
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if DATABASE_URL else "?"

    cursor.execute(
        f"SELECT user_id, game_balance, bonus_balance FROM users WHERE user_id = {ph}",
        (user_id,),
    )
    row = cursor.fetchone()

    if not row:
        cursor.execute(
            f"INSERT INTO users (user_id, username, first_name, game_balance, bonus_balance) VALUES ({ph}, {ph}, {ph}, 0, 0)",
            (user_id, username, first_name),
        )
        conn.commit()
        game_bal, bonus_bal = 0, 0
    else:
        game_bal, bonus_bal = row[1], row[2]
        cursor.execute(
            f"UPDATE users SET username = {ph}, first_name = {ph} WHERE user_id = {ph}",
            (username, first_name, user_id),
        )
        conn.commit()

    cursor.close()
    conn.close()
    return {"game_balance": game_bal, "bonus_balance": bonus_bal}


def update_balances(user_id: int, game_diff: int = 0, bonus_diff: int = 0):
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if DATABASE_URL else "?"

    cursor.execute(
        f"""
        UPDATE users
        SET game_balance = game_balance + {ph}, bonus_balance = bonus_balance + {ph}
        WHERE user_id = {ph}
        """,
        (game_diff, bonus_diff, user_id),
    )
    conn.commit()

    cursor.execute(
        f"SELECT game_balance, bonus_balance FROM users WHERE user_id = {ph}",
        (user_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return {"game_balance": row[0], "bonus_balance": row[1]}


async def send_telegram_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            pass


async def send_telegram_gift(user_id: int, gift_id: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendGift"
    payload = {"user_id": user_id, "gift_id": gift_id}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            res_data = await response.json()
            if res_data.get("ok"):
                return True
            print(f"Ошибка API sendGift: {res_data.get('description')}")
            return False


async def refund_real_stars(user_id: int) -> dict:
    if not DATABASE_URL:
        return {"refunded_count": 0, "refunded_stars": 0, "errors": ["DATABASE_URL не задан"]}

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, telegram_payment_charge_id, total_amount
        FROM payments
        WHERE user_id = %s AND refunded = FALSE
        ORDER BY id ASC
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return {"refunded_count": 0, "refunded_stars": 0, "errors": []}

    refunded_ids = []
    refunded_stars = 0
    errors = []

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/refundStarPayment"

    async with aiohttp.ClientSession() as session:
        for row_id, charge_id, total_amount in rows:
            if not charge_id:
                errors.append(f"Платёж #{row_id}: отсутствует telegram_payment_charge_id")
                continue

            payload = {
                "user_id": user_id,
                "telegram_payment_charge_id": charge_id,
            }
            async with session.post(url, json=payload) as resp:
                data = await resp.json()

            if data.get("ok"):
                refunded_ids.append(row_id)
                refunded_stars += int(total_amount)
            else:
                errors.append(f"Платёж #{row_id} ({charge_id}): {data.get('description', 'ошибка API')}")

    if refunded_ids:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE payments
            SET refunded = TRUE
            WHERE id = ANY(%s)
            """,
            (refunded_ids,),
        )
        conn.commit()
        cursor.close()
        conn.close()

    return {
        "refunded_count": len(refunded_ids),
        "refunded_stars": refunded_stars,
        "errors": errors,
    }


class ActionRequest(BaseModel):
    user_id: int
    reward: int = 0
    username: str = ""
    first_name: str = ""


class SpinRequest(BaseModel):
    user_id: int
    bet: int
    username: str = ""
    first_name: str = ""


class InvoiceRequest(BaseModel):
    amount: int


class WithdrawRequest(BaseModel):
    user_id: int
    type: str
    gift_id: str
    amount: int


class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[dict] = None
    pre_checkout_query: Optional[dict] = None


@app.get("/api/get_balance")
def api_get_balance(user_id: int, username: str = "", first_name: str = ""):
    return get_or_create_user(user_id, username, first_name)


@app.post("/api/add_reward")
def api_add_reward(data: ActionRequest):
    balances = update_balances(data.user_id, bonus_diff=data.reward)
    return {"success": True, **balances}


@app.get("/api/get_gifts")
async def api_get_gifts():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getAvailableGifts"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            res = await response.json()
            if res.get("ok"):
                gifts = res.get("result", {}).get("gifts", [])
                enriched_gifts = [
                    {**gift, "display_name": format_gift_name(gift, idx)}
                    for idx, gift in enumerate(gifts)
                ]
                return {"success": True, "gifts": enriched_gifts}
            return {"success": False, "error": res.get("description", "Не удалось загрузить подарки")}


@app.post("/api/create_invoice")
async def api_create_invoice(data: InvoiceRequest):
    if not (1 <= data.amount <= 10000):
        raise HTTPException(status_code=400, detail="Неверная сумма")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink"
    payload = {
        "title": "Пополнение игрового баланса",
        "description": f"Зачисление {data.amount} ⭐ на игровой баланс StarYield",
        "payload": f"topup_{data.amount}_{random.randint(1000, 9999)}",
        "currency": "XTR",
        "prices": [{"label": "Звёзды Telegram", "amount": data.amount}],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            res = await response.json()
            if res.get("ok"):
                return {"invoice_link": res["result"]}
            return JSONResponse(status_code=400, content={"error": res.get("description", "Ошибка инвойса")})


@app.post("/api/spin_wheel")
def api_spin_wheel(data: SpinRequest):
    bet = data.bet
    if not (1 <= bet <= 1000):
        raise HTTPException(status_code=400, detail="Неверная ставка")

    user_data = get_or_create_user(data.user_id, data.username, data.first_name)
    if user_data["game_balance"] < bet:
        return {"success": False, "error": "Недостаточно звёзд на балансе!"}

    balances = update_balances(data.user_id, game_diff=-bet)

    clamped = min(bet, 1000)
    chance = min(0.00999 * (clamped / 1000) ** 0.7, 0.00999)
    is_win = random.random() < chance
    prize = 0

    if is_win:
        prize = bet * 2
        balances = update_balances(data.user_id, game_diff=prize)

    return {
        "success": True,
        "won": is_win,
        "prize": prize,
        **balances,
    }


@app.post("/api/withdraw")
async def api_withdraw(data: WithdrawRequest):
    user_data = get_or_create_user(data.user_id)

    if data.type == "game":
        game_bal = user_data["game_balance"]

        if data.amount < 15:
            return {"success": False, "error": "Минимальная стоимость подарка для вывода: 15 ⭐"}

        if game_bal < data.amount:
            return {"success": False, "error": f"Недостаточно звёзд! У вас {game_bal} ⭐, а нужно {data.amount} ⭐."}

        if not data.gift_id:
            return {"success": False, "error": "Выберите конкретный подарок для вывода!"}

        new_balances = update_balances(data.user_id, game_diff=-data.amount)
        success_gift = await send_telegram_gift(data.user_id, data.gift_id)

        if success_gift:
            return {
                "success": True,
                "message": f"Подарок стоимостью {data.amount} ⭐ успешно отправлен вам в чат!",
                **new_balances,
            }

        update_balances(data.user_id, game_diff=data.amount)
        return {"success": False, "error": "Ошибка отправки подарка. Проверьте баланс кассы бота."}

    if data.type == "bonus":
        if user_data["bonus_balance"] < 500:
            return {"success": False, "error": "Минимальный вывод с Бонусного баланса: 500 ⭐."}
        return {"success": True, "message": "Заявка на вывод бонусного баланса принята!"}

    return {"success": False, "error": "Неизвестный тип баланса"}


@app.post("/webhook")
async def telegram_webhook(update: TelegramUpdate):
    if update.pre_checkout_query:
        query_id = update.pre_checkout_query.get("id")
        if query_id:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerPreCheckoutQuery"
            payload = {"pre_checkout_query_id": query_id, "ok": True}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    pass
        return {"ok": True}

    if not update.message:
        return {"ok": True}

    message = update.message
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    user = message.get("from", {})
    user_id = user.get("id")
    username = user.get("username", "")
    first_name = user.get("first_name", "")

    successful_payment = message.get("successful_payment")
    if successful_payment and user_id:
        amount = int(successful_payment.get("total_amount", 0))
        charge_id = successful_payment.get("telegram_payment_charge_id", "")
        currency = successful_payment.get("currency", "XTR")
        if amount > 0:
            get_or_create_user(user_id, username, first_name)
            save_payment(user_id, charge_id, amount, currency)
            update_balances(user_id, game_diff=amount)
            if chat_id:
                await send_telegram_message(
                    chat_id,
                    f"✅ Оплата прошла! На игровой баланс зачислено {amount} ⭐.",
                )
        return {"ok": True}

    if text == "/refund_real_stars" and user_id and chat_id:
        if user_id != ADMIN_ID:
            await send_telegram_message(chat_id, "⛔ Эта команда доступна только администратору.")
            return {"ok": True}

        res = await refund_real_stars(user_id)
        msg = (
            f"💸 Возвращено транзакций: {res['refunded_count']}\n"
            f"⭐ Вернулось на баланс Telegram: {res['refunded_stars']}"
        )
        if res["errors"]:
            msg += "\n\n⚠️ Ошибки:\n" + "\n".join(res["errors"])
        await send_telegram_message(chat_id, msg)
        return {"ok": True}

    if text == "/start" and user_id and chat_id:
        get_or_create_user(user_id, username, first_name)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "👋 Привет! Добро пожаловать в StarYield.\n\nНажми на кнопку ниже, чтобы открыть мини-приложение:",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🚀 Открыть StarYield", "web_app": {"url": WEBAPP_URL}}]
                ]
            },
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                pass

    return {"ok": True}


app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
