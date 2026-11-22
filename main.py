import asyncio
import os
import random
import time
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

BOT_TOKEN = os.getenv("BOT_TOKEN", "9187717570:AAFe52G8d-aVNkwFet3tr9yw9deRqFrDG9Q")
WEBAPP_URL = "https://star-yield-bot.onrender.com"
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = 7449913629

TG_TIMEOUT = aiohttp.ClientTimeout(total=6)
AVATAR_CACHE: dict[int, tuple[float, bytes, str]] = {}
AVATAR_CACHE_TTL = 300.0

# Курс перевода бонусных звёзд в игровые (1.0 = 1:1, 0.8 = -20% комиссия)
BONUS_TO_GAME_RATE = 1.0
MIN_BONUS_TRANSFER = 1

# Линейка из 5 цветных билетов:
# price — стоимость в game_balance
# outcomes — список кортежей (reward_stars, weight, label)
# Веса заданы в процентах (сумма = 100 в каждом билете)
TICKETS = {
    "gray": {
        "id": "gray",
        "name": "Серый билет",
        "color": "#8e929b",
        "price": 5,
        "outcomes": [
            (0, 1.0, "Пусто — повезёт в следующий раз"),
            (3, 44.0, "3 ⭐"),
            (4, 31.0, "4 ⭐"),
            (6, 17.0, "6 ⭐"),
            (9, 5.5, "9 ⭐"),
            (15, 1.5, "15 ⭐ Джекпот!"),
        ],
    },
    "blue": {
        "id": "blue",
        "name": "Синий билет",
        "color": "#3b82f6",
        "price": 15,
        "outcomes": [
            (0, 0.8, "Пусто"),
            (12, 43.2, "12 ⭐"),
            (14, 32.0, "14 ⭐"),
            (18, 17.0, "18 ⭐"),
            (26, 5.5, "26 ⭐"),
            (45, 1.5, "45 ⭐ Джекпот!"),
        ],
    },
    "burgundy": {
        "id": "burgundy",
        "name": "Бордовый билет",
        "color": "#881337",
        "price": 35,
        "outcomes": [
            (0, 0.6, "Пусто"),
            (29, 43.4, "29 ⭐"),
            (33, 32.0, "33 ⭐"),
            (42, 17.0, "42 ⭐"),
            (60, 5.6, "60 ⭐"),
            (105, 1.4, "105 ⭐ Джекпот!"),
        ],
    },
    "purple": {
        "id": "purple",
        "name": "Фиолетовый билет",
        "color": "#9333ea",
        "price": 75,
        "outcomes": [
            (0, 0.4, "Пусто"),
            (64, 43.6, "64 ⭐"),
            (72, 32.0, "72 ⭐"),
            (90, 17.0, "90 ⭐"),
            (130, 5.7, "130 ⭐"),
            (225, 1.3, "225 ⭐ Джекпот!"),
        ],
    },
    "gold": {
        "id": "gold",
        "name": "Золотой билет",
        "color": "#eab308",
        "price": 150,
        "outcomes": [
            (0, 0.25, "Пусто"),
            (130, 43.75, "130 ⭐"),
            (145, 32.0, "145 ⭐"),
            (180, 17.0, "180 ⭐"),
            (260, 5.8, "260 ⭐"),
            (450, 1.2, "450 ⭐ Джекпот!"),
        ],
    },
}

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


class AsyncRequestGuard:
    """
    Защита от:
    - параллельных запросов по одному user_id и бакету;
    - кликеров/спама с одного аккаунта (min_interval_sec);
    - резкого наплыва множества пользователей (семафор одновременных операций).
    """

    def __init__(self, max_concurrent: int = 12, min_interval_sec: float = 0.7):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()
        self._last_hit: dict[tuple[int, str], float] = {}
        self._in_flight: set[tuple[int, str]] = set()
        self._min_interval = min_interval_sec
        self._counter = 0

    async def _cleanup_stale(self, now: float) -> None:
        self._counter += 1
        if self._counter % 500 != 0:
            return
        ttl = max(self._min_interval * 15, 15.0)
        stale = [k for k, ts in self._last_hit.items() if now - ts > ttl]
        for k in stale:
            del self._last_hit[k]

    async def protect(self, user_id: int, bucket: str = "wallet", min_interval: float | None = None, acquire_timeout: float = 0.15):
        class _GuardContext:
            def __init__(self, outer: "AsyncRequestGuard"):
                self._outer = outer
                self._acquired = False
                self._key: tuple[int, str] | None = None

            async def __aenter__(self):
                now = time.monotonic()
                interval = self._outer._min_interval if min_interval is None else min_interval
                key = (int(user_id), bucket)

                async with self._outer._lock:
                    await self._outer._cleanup_stale(now)

                    if key in self._outer._in_flight:
                        return False, "Предыдущий запрос ещё обрабатывается"

                    prev = self._outer._last_hit.get(key, 0.0)
                    if now - prev < interval:
                        return False, "Слишком частые запросы, подожди секунду"

                    try:
                        await asyncio.wait_for(self._outer._semaphore.acquire(), timeout=acquire_timeout)
                    except asyncio.TimeoutError:
                        return False, "Сервер сейчас загружен, попробуй через секунду"

                    self._outer._in_flight.add(key)
                    self._outer._last_hit[key] = now
                    self._acquired = True
                    self._key = key
                    return True, None

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if self._acquired and self._key is not None:
                    async with self._outer._lock:
                        self._outer._in_flight.discard(self._key)
                    self._outer._semaphore.release()
                return False

        return _GuardContext(self)


guard = AsyncRequestGuard(max_concurrent=12, min_interval_sec=0.7)


def format_gift_name(gift: dict, index: int) -> str:
    emoji = (gift.get("sticker") or {}).get("emoji") or "🎁"
    if emoji in GIFT_EMOJI_NAMES:
        return f"{emoji} {GIFT_EMOJI_NAMES[emoji]}"
    return f"{emoji} Подарок #{index + 1}"


def roll_ticket_outcome(ticket_id: str) -> tuple[int, str]:
    ticket = TICKETS[ticket_id]
    outcomes = ticket["outcomes"]
    weights = [item[1] for item in outcomes]
    chosen = random.choices(outcomes, weights=weights, k=1)[0]
    reward_stars, _, label = chosen
    return int(reward_stars), label


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
        game_bal, bonus_bal = int(row[1] or 0), int(row[2] or 0)
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

    if DATABASE_URL:
        cursor.execute(
            f"""
            UPDATE users
            SET game_balance = GREATEST(0, game_balance + {ph}),
                bonus_balance = GREATEST(0, bonus_balance + {ph})
            WHERE user_id = {ph}
            """,
            (game_diff, bonus_diff, user_id),
        )
    else:
        cursor.execute(
            f"""
            UPDATE users
            SET game_balance = MAX(0, game_balance + {ph}),
                bonus_balance = MAX(0, bonus_balance + {ph})
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
    return {"game_balance": int(row[0] or 0), "bonus_balance": int(row[1] or 0)}


def try_spend_balances(user_id: int, game_spend: int = 0, bonus_spend: int = 0) -> Optional[dict]:
    """
    Атомарно списывает game_spend и/или bonus_spend, только если хватает средств.
    Возвращает новый словарь балансов или None, если звёзд недостаточно.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if DATABASE_URL else "?"

    try:
        cursor.execute(
            f"""
            UPDATE users
            SET game_balance = game_balance - {ph},
                bonus_balance = bonus_balance - {ph}
            WHERE user_id = {ph}
              AND game_balance >= {ph}
              AND bonus_balance >= {ph}
            RETURNING game_balance, bonus_balance
            """,
            (game_spend, bonus_spend, user_id, game_spend, bonus_spend),
        )
        row = cursor.fetchone()
        conn.commit()
    except Exception:
        cursor.execute(
            f"""
            UPDATE users
            SET game_balance = game_balance - {ph},
                bonus_balance = bonus_balance - {ph}
            WHERE user_id = {ph}
              AND game_balance >= {ph}
              AND bonus_balance >= {ph}
            """,
            (game_spend, bonus_spend, user_id, game_spend, bonus_spend),
        )
        updated = cursor.rowcount
        conn.commit()
        if not updated:
            cursor.close()
            conn.close()
            return None
        cursor.execute(
            f"SELECT game_balance, bonus_balance FROM users WHERE user_id = {ph}",
            (user_id,),
        )
        row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        return None

    return {"game_balance": int(row[0] or 0), "bonus_balance": int(row[1] or 0)}


async def send_telegram_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    async with aiohttp.ClientSession(timeout=TG_TIMEOUT) as session:
        async with session.post(url, json=payload) as resp:
            pass


async def send_telegram_gift(user_id: int, gift_id: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendGift"
    payload = {"user_id": user_id, "gift_id": gift_id}
    async with aiohttp.ClientSession(timeout=TG_TIMEOUT) as session:
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

    async with aiohttp.ClientSession(timeout=TG_TIMEOUT) as session:
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


class OpenTicketRequest(BaseModel):
    user_id: int
    ticket_id: str
    username: str = ""
    first_name: str = ""


class BonusTransferRequest(BaseModel):
    user_id: int
    amount: int
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


@app.get("/api/avatar/{target_user_id}")
async def api_get_avatar(target_user_id: int):
    now = time.monotonic()
    cached = AVATAR_CACHE.get(target_user_id)
    if cached and (now - cached[0]) < AVATAR_CACHE_TTL:
        return Response(content=cached[1], media_type=cached[2])

    try:
        async with aiohttp.ClientSession(timeout=TG_TIMEOUT) as session:
            photos_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUserProfilePhotos"
            async with session.get(photos_url, params={"user_id": target_user_id, "limit": 1}) as resp:
                photos_data = await resp.json()

            if not photos_data.get("ok"):
                raise HTTPException(status_code=404, detail="Avatar not available")

            photos = (photos_data.get("result") or {}).get("photos") or []
            if not photos or not photos[0]:
                raise HTTPException(status_code=404, detail="No avatar")

            best_photo = photos[0][-1]
            file_id = best_photo.get("file_id")
            if not file_id:
                raise HTTPException(status_code=404, detail="No file_id")

            file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
            async with session.get(file_url, params={"file_id": file_id}) as f_resp:
                file_data = await f_resp.json()

            file_path = ((file_data.get("result") or {}).get("file_path")) or ""
            if not file_data.get("ok") or not file_path:
                raise HTTPException(status_code=404, detail="No file_path")

            download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            async with session.get(download_url) as img_resp:
                if img_resp.status != 200:
                    raise HTTPException(status_code=404, detail="Failed to download avatar")
                img_bytes = await img_resp.read()
                content_type = img_resp.headers.get("Content-Type", "image/jpeg")

        AVATAR_CACHE[target_user_id] = (now, img_bytes, content_type)
        return Response(content=img_bytes, media_type=content_type)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Ошибка загрузки аватарки {target_user_id}: {e}")
        raise HTTPException(status_code=404, detail="Avatar error")


@app.get("/api/get_balance")
def api_get_balance(user_id: int, username: str = "", first_name: str = ""):
    return get_or_create_user(user_id, username, first_name)


@app.post("/api/add_reward")
async def api_add_reward(data: ActionRequest):
    if data.reward < 0:
        raise HTTPException(status_code=400, detail="Награда не может быть отрицательной")

    async with await guard.protect(data.user_id, bucket="reward", min_interval=0.8) as (ok, reason):
        if not ok:
            return JSONResponse(status_code=429, content={"success": False, "error": reason})

        get_or_create_user(data.user_id, data.username, data.first_name)
        balances = update_balances(data.user_id, bonus_diff=data.reward)
        return {"success": True, **balances}


@app.post("/api/transfer_bonus")
async def api_transfer_bonus(data: BonusTransferRequest):
    """Односторонний перевод: bonus_balance -> game_balance (обратный перевод запрещён)."""
    if data.amount < MIN_BONUS_TRANSFER:
        raise HTTPException(
            status_code=400,
            detail=f"Минимальная сумма перевода: {MIN_BONUS_TRANSFER} бонусных ⭐",
        )

    async with await guard.protect(data.user_id, bucket="wallet", min_interval=0.8) as (ok, reason):
        if not ok:
            return JSONResponse(status_code=429, content={"success": False, "error": reason})

        get_or_create_user(data.user_id, data.username, data.first_name)
        game_received = int(data.amount * BONUS_TO_GAME_RATE)
        if game_received <= 0:
            return {"success": False, "error": "Сумма слишком мала для конвертации в игровой баланс"}

        spent = try_spend_balances(data.user_id, bonus_spend=data.amount)
        if spent is None:
            return {"success": False, "error": "Недостаточно бонусных звёзд!"}

        balances = update_balances(data.user_id, game_diff=game_received)
        return {
            "success": True,
            "spent_bonus": data.amount,
            "received_game": game_received,
            **balances,
        }


@app.get("/api/tickets")
def api_get_tickets():
    return {
        "success": True,
        "tickets": [
            {
                "id": t["id"],
                "name": t["name"],
                "color": t["color"],
                "price": t["price"],
                "prizes": [item[2] for item in t["outcomes"] if item[0] > 0],
            }
            for t in TICKETS.values()
        ],
    }


@app.post("/api/open_ticket")
async def api_open_ticket(data: OpenTicketRequest):
    ticket_key = (data.ticket_id or "").strip().lower()
    if ticket_key not in TICKETS:
        raise HTTPException(status_code=400, detail="Неизвестный тип билета")

    ticket = TICKETS[ticket_key]
    price = int(ticket["price"])

    async with await guard.protect(data.user_id, bucket="wallet", min_interval=0.7) as (ok, reason):
        if not ok:
            return JSONResponse(status_code=429, content={"success": False, "error": reason})

        get_or_create_user(data.user_id, data.username, data.first_name)
        after_spend = try_spend_balances(data.user_id, game_spend=price)
        if after_spend is None:
            return {
                "success": False,
                "error": f"Недостаточно звёзд на игровом балансе! Нужно {price} ⭐.",
            }

        reward_stars, label = roll_ticket_outcome(ticket_key)
        balances = (
            update_balances(data.user_id, game_diff=reward_stars)
            if reward_stars > 0
            else after_spend
        )

        return {
            "success": True,
            "ticket_id": ticket_key,
            "ticket_name": ticket["name"],
            "price": price,
            "won": reward_stars > 0,
            "prize": reward_stars,
            "label": label,
            **balances,
        }


@app.get("/api/get_gifts")
async def api_get_gifts():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getAvailableGifts"
    async with aiohttp.ClientSession(timeout=TG_TIMEOUT) as session:
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

    async with aiohttp.ClientSession(timeout=TG_TIMEOUT) as session:
        async with session.post(url, json=payload) as response:
            res = await response.json()
            if res.get("ok"):
                return {"invoice_link": res["result"]}
            return JSONResponse(status_code=400, content={"error": res.get("description", "Ошибка инвойса")})


@app.post("/api/spin_wheel")
async def api_spin_wheel(data: SpinRequest):
    bet = data.bet
    if not (1 <= bet <= 1000):
        raise HTTPException(status_code=400, detail="Неверная ставка")

    async with await guard.protect(data.user_id, bucket="wallet", min_interval=0.7) as (ok, reason):
        if not ok:
            return JSONResponse(status_code=429, content={"success": False, "error": reason})

        get_or_create_user(data.user_id, data.username, data.first_name)
        after_spend = try_spend_balances(data.user_id, game_spend=bet)
        if after_spend is None:
            return {"success": False, "error": "Недостаточно звёзд на балансе!"}

        clamped = min(bet, 1000)
        chance = min(0.00999 * (clamped / 1000) ** 0.7, 0.00999)
        is_win = random.random() < chance
        prize = 0

        if is_win:
            prize = bet * 2
            balances = update_balances(data.user_id, game_diff=prize)
        else:
            balances = after_spend

        return {
            "success": True,
            "won": is_win,
            "prize": prize,
            **balances,
        }


@app.post("/api/withdraw")
async def api_withdraw(data: WithdrawRequest):
    async with await guard.protect(data.user_id, bucket="wallet", min_interval=1.0) as (ok, reason):
        if not ok:
            return JSONResponse(status_code=429, content={"success": False, "error": reason})

        get_or_create_user(data.user_id)

        if data.type == "game":
            if data.amount < 15:
                return {"success": False, "error": "Минимальная стоимость подарка для вывода: 15 ⭐"}

            if not data.gift_id:
                return {"success": False, "error": "Выберите конкретный подарок для вывода!"}

            new_balances = try_spend_balances(data.user_id, game_spend=data.amount)
            if new_balances is None:
                current = get_or_create_user(data.user_id)
                return {
                    "success": False,
                    "error": f"Недостаточно звёзд! У вас {current['game_balance']} ⭐, а нужно {data.amount} ⭐.",
                }

            success_gift = await send_telegram_gift(data.user_id, data.gift_id)

            if success_gift:
                return {
                    "success": True,
                    "message": f"Подарок стоимостью {data.amount} ⭐ успешно отправлен вам в чат!",
                    **new_balances,
                }

            restored = update_balances(data.user_id, game_diff=data.amount)
            return {
                "success": False,
                "error": "Ошибка отправки подарка. Проверьте баланс кассы бота.",
                **restored,
            }

        if data.type == "bonus":
            current = get_or_create_user(data.user_id)
            if current["bonus_balance"] < 500:
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
            async with aiohttp.ClientSession(timeout=TG_TIMEOUT) as session:
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
        async with aiohttp.ClientSession(timeout=TG_TIMEOUT) as session:
            async with session.post(url, json=payload) as resp:
                pass

    return {"ok": True}


app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
