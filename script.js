const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const user = tg.initDataUnsafe?.user || {};
const userId = user.id || 123456789;
const username = user.username || "";
const firstName = user.first_name || "Игрок";

const TICKET_UI = {
    gray: {
        id: "gray",
        name: "Серый билет",
        price: 5,
        color: "#8e929b"
    },
    blue: {
        id: "blue",
        name: "Синий билет",
        price: 15,
        color: "#3b82f6"
    },
    burgundy: {
        id: "burgundy",
        name: "Бордовый билет",
        price: 35,
        color: "#881337"
    },
    purple: {
        id: "purple",
        name: "Фиолетовый билет",
        price: 75,
        color: "#9333ea"
    },
    gold: {
        id: "gold",
        name: "Золотой билет",
        price: 150,
        color: "#eab308"
    }
};

let selectedTicketId = "gray";
let isOpeningTicket = false;
let isWithdrawingGift = false;
let isTransferringBonus = false;

document.addEventListener("DOMContentLoaded", () => {
    const nameEl = document.getElementById("user-name");
    const avatarEl = document.getElementById("user-avatar");

    if (nameEl) nameEl.textContent = firstName;
    if (avatarEl && firstName) {
        avatarEl.textContent = firstName.charAt(0).toUpperCase();
    }

    updateTicketPreview(selectedTicketId);
    loadBalance();
});

function switchTab(tabName) {
    const tabTasks = document.getElementById("tab-tasks");
    const tabGames = document.getElementById("tab-games");
    const tabProfile = document.getElementById("tab-profile");
    const viewTasks = document.getElementById("view-tasks");
    const viewGames = document.getElementById("view-games");
    const viewProfile = document.getElementById("view-profile");

    tabTasks.classList.remove("active");
    tabGames.classList.remove("active");
    tabProfile.classList.remove("active");
    viewTasks.classList.remove("active");
    viewGames.classList.remove("active");
    viewProfile.classList.remove("active");

    if (tabName === "tasks") {
        tabTasks.classList.add("active");
        viewTasks.classList.add("active");
    } else if (tabName === "games") {
        tabGames.classList.add("active");
        viewGames.classList.add("active");
    } else {
        tabProfile.classList.add("active");
        viewProfile.classList.add("active");
    }

    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred("light");
    }
}

function renderBalances(data) {
    if (data.game_balance !== undefined) {
        document.getElementById("game-balance-amount").textContent = data.game_balance;
    }
    if (data.bonus_balance !== undefined) {
        document.getElementById("bonus-balance-amount").textContent = data.bonus_balance;
    }
}

async function loadBalance() {
    try {
        const params = new URLSearchParams({ user_id: userId, username, first_name: firstName });
        const response = await fetch(`/api/get_balance?${params.toString()}`);
        const data = await response.json();
        renderBalances(data);
    } catch (error) {
        console.error("Ошибка загрузки баланса:", error);
    }
}

async function completeTask(reward, btnElement) {
    if (btnElement) btnElement.disabled = true;
    try {
        const response = await fetch("/api/add_reward", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, reward, username, first_name: firstName })
        });
        const data = await response.json();
        if (data.success) {
            renderBalances(data);
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        }
    } catch (error) {
        console.error("Ошибка:", error);
    } finally {
        if (btnElement) setTimeout(() => btnElement.disabled = false, 600);
    }
}

function updateTicketPreview(ticketId) {
    const info = TICKET_UI[ticketId] || TICKET_UI.gray;
    const badgeEl = document.getElementById("stage-badge");
    const titleEl = document.getElementById("stage-title");
    const openBtn = document.getElementById("open-ticket-btn");
    const stageEl = document.getElementById("ticket-stage");

    if (badgeEl) {
        badgeEl.textContent = `${info.name.toUpperCase()} • ${info.price} ⭐`;
        badgeEl.style.border = `1px solid ${info.color}`;
    }
    if (titleEl && !isOpeningTicket) {
        titleEl.textContent = "Готов к открытию";
    }
    if (openBtn) {
        openBtn.textContent = `Открыть ${info.name} (${info.price} ⭐)`;
    }
    if (stageEl) {
        stageEl.style.borderColor = info.color;
    }
}

function selectTicket(ticketId, btnElement) {
    if (isOpeningTicket || !TICKET_UI[ticketId]) return;
    selectedTicketId = ticketId;

    document.querySelectorAll(".ticket-item").forEach(item => {
        item.classList.remove("active");
        item.style.borderColor = "rgba(255, 255, 255, 0.12)";
    });

    if (btnElement) {
        btnElement.classList.add("active");
        btnElement.style.borderColor = TICKET_UI[ticketId].color;
    }

    updateTicketPreview(ticketId);
    if (tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
}

async function openBonusTransferPrompt() {
    if (isTransferringBonus) return;

    const bonusBal = parseInt(document.getElementById("bonus-balance-amount").textContent) || 0;
    if (bonusBal <= 0) {
        if (tg.showAlert) tg.showAlert("На Бонусном балансе пока 0 ⭐.");
        else alert("На Бонусном балансе пока 0 ⭐.");
        return;
    }

    const raw = prompt(
        `Перевод с Бонусного баланса на Игровой (обратный перевод невозможен).\nДоступно бонусов: ${bonusBal} ⭐`,
        String(bonusBal)
    );
    if (!raw) return;

    const amount = parseInt(raw, 10);
    if (isNaN(amount) || amount < 1 || amount > bonusBal) {
        if (tg.showAlert) tg.showAlert(`Введите число от 1 до ${bonusBal} ⭐`);
        else alert(`Введите число от 1 до ${bonusBal} ⭐`);
        return;
    }

    isTransferringBonus = true;
    try {
        const res = await fetch("/api/transfer_bonus", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: userId,
                amount,
                username,
                first_name: firstName
            })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            renderBalances(data);
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
            const msg = `Переведено ${data.spent_bonus} бонусных ⭐ → +${data.received_game} игровых ⭐.`;
            if (tg.showAlert) tg.showAlert(msg);
            else alert(msg);
        } else {
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
            const errMsg = data.error || "Ошибка перевода бонусов";
            if (tg.showAlert) tg.showAlert(errMsg);
            else alert(errMsg);
        }
    } catch (e) {
        console.error("Ошибка перевода бонусов:", e);
        if (tg.showAlert) tg.showAlert("Ошибка соединения с сервером");
    } finally {
        isTransferringBonus = false;
    }
}

async function openTopupPrompt() {
    const raw = prompt("Сколько звёзд Telegram (⭐) зачислить на Игровой баланс? (от 1 до 10000)", "15");
    if (!raw) return;
    const amount = parseInt(raw, 10);
    if (isNaN(amount) || amount < 1 || amount > 10000) {
        if (tg.showAlert) tg.showAlert("Введите корректное число от 1 до 10000 ⭐");
        return;
    }

    try {
        const res = await fetch("/api/create_invoice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ amount })
        });
        const data = await res.json();
        if (data.invoice_link && tg.openInvoice) {
            tg.openInvoice(data.invoice_link, (status) => {
                if (status === "paid") {
                    if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
                    setTimeout(loadBalance, 800);
                }
            });
        } else {
            if (tg.showAlert) tg.showAlert(data.error || "Ошибка создания счёта");
        }
    } catch (e) {
        console.error("Ошибка оплаты:", e);
    }
}

async function openSelectedTicket() {
    if (isOpeningTicket) return;

    const ticketInfo = TICKET_UI[selectedTicketId] || TICKET_UI.gray;
    const gameBalance = parseInt(document.getElementById("game-balance-amount").textContent) || 0;

    if (gameBalance < ticketInfo.price) {
        const msg = `Недостаточно звёзд для билета «${ticketInfo.name}» (${ticketInfo.price} ⭐).`;
        if (tg.showAlert) tg.showAlert(msg);
        else alert(msg);
        return;
    }

    isOpeningTicket = true;
    const openBtn = document.getElementById("open-ticket-btn");
    const statusEl = document.getElementById("game-status");
    const stageEl = document.getElementById("ticket-stage");
    const stageTitleEl = document.getElementById("stage-title");

    if (openBtn) openBtn.disabled = true;
    if (stageEl) stageEl.classList.add("opening");
    if (stageTitleEl) stageTitleEl.textContent = "Стираем защитный слой...";
    if (statusEl) statusEl.textContent = `Открываем ${ticketInfo.name}...`;

    let resultData = null;
    try {
        const res = await fetch("/api/open_ticket", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: userId,
                ticket_id: selectedTicketId,
                username,
                first_name: firstName
            })
        });
        resultData = await res.json();

        if (!res.ok || !resultData.success) {
            isOpeningTicket = false;
            if (openBtn) openBtn.disabled = false;
            if (stageEl) stageEl.classList.remove("opening");
            if (stageTitleEl) stageTitleEl.textContent = "Готов к открытию";
            const errText = resultData.error || "Ошибка открытия билета";
            if (statusEl) statusEl.textContent = errText;
            if (tg.showAlert) tg.showAlert(errText);
            return;
        }
    } catch (e) {
        isOpeningTicket = false;
        if (openBtn) openBtn.disabled = false;
        if (stageEl) stageEl.classList.remove("opening");
        if (stageTitleEl) stageTitleEl.textContent = "Готов к открытию";
        if (statusEl) statusEl.textContent = "Ошибка соединения с сервером";
        return;
    }

    const balanceAfterBuy = resultData.won
        ? Math.max(0, resultData.game_balance - resultData.prize)
        : resultData.game_balance;
    document.getElementById("game-balance-amount").textContent = balanceAfterBuy;

    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred("medium");
    }

    setTimeout(() => {
        isOpeningTicket = false;
        if (openBtn) openBtn.disabled = false;
        if (stageEl) stageEl.classList.remove("opening");
        renderBalances(resultData);

        if (resultData.won) {
            if (stageTitleEl) stageTitleEl.textContent = `Выигрыш: ${resultData.label}`;
            if (statusEl) {
                statusEl.textContent = `🎉 ${ticketInfo.name}: выпало ${resultData.label} (+${resultData.prize} ⭐)!`;
            }
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        } else {
            if (stageTitleEl) stageTitleEl.textContent = "Пусто";
            if (statusEl) {
                statusEl.textContent = `😢 ${ticketInfo.name}: пусто (-${ticketInfo.price} ⭐). Попробуй ещё раз!`;
            }
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
        }
    }, 900);
}

function closeGiftModal() {
    const modal = document.getElementById("gift-withdraw-modal");
    if (modal) modal.remove();
}

async function submitGiftWithdraw(giftId, amount) {
    if (isWithdrawingGift) return;
    isWithdrawingGift = true;

    try {
        const res = await fetch("/api/withdraw", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: userId,
                type: "game",
                gift_id: String(giftId),
                amount: Number(amount)
            })
        });
        const data = await res.json();

        if (data.success) {
            renderBalances(data);
            closeGiftModal();
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
            if (tg.showAlert) tg.showAlert(data.message || `Подарок за ${amount} ⭐ отправлен!`);
            else alert(data.message || `Подарок за ${amount} ⭐ отправлен!`);
        } else {
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
            if (tg.showAlert) tg.showAlert(data.error || "Ошибка вывода подарка");
            else alert(data.error || "Ошибка вывода подарка");
        }
    } catch (e) {
        console.error("Ошибка вывода:", e);
        if (tg.showAlert) tg.showAlert("Ошибка соединения с сервером");
    } finally {
        isWithdrawingGift = false;
    }
}

async function openGiftWithdrawModal(gameBal) {
    closeGiftModal();

    const modal = document.createElement("div");
    modal.id = "gift-withdraw-modal";
    modal.style.cssText = `
        position: fixed; inset: 0; background: rgba(0,0,0,0.75);
        display: flex; align-items: center; justify-content: center;
        z-index: 9999; padding: 16px;
    `;

    const box = document.createElement("div");
    box.style.cssText = `
        width: 100%; max-width: 380px; max-height: 80vh; overflow-y: auto;
        background: #181c24; color: #fff; border-radius: 16px; padding: 16px;
        border: 1px solid rgba(255,255,255,0.12);
    `;

    box.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <div style="font-weight:700; font-size:16px;">🎁 Вывод подарком (${gameBal} ⭐)</div>
            <button id="close-gift-modal-btn" style="background:#2a303c; color:#fff; border:none; border-radius:8px; padding:4px 10px; cursor:pointer;">✕</button>
        </div>
        <div id="gifts-list-container" style="color:#aaa; font-size:14px;">Загружаем подарки Telegram...</div>
    `;

    modal.appendChild(box);
    document.body.appendChild(modal);

    document.getElementById("close-gift-modal-btn").onclick = closeGiftModal;
    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeGiftModal();
    });

    const container = document.getElementById("gifts-list-container");

    try {
        const res = await fetch("/api/get_gifts");
        const data = await res.json();

        if (!data.success || !Array.isArray(data.gifts)) {
            container.innerHTML = `<div style="color:#ff6b6b;">${data.error || "Не удалось получить список подарков"}</div>`;
            return;
        }

        const available = data.gifts
            .filter(g => (g.star_count || 0) >= 15)
            .sort((a, b) => (a.star_count || 0) - (b.star_count || 0));

        if (!available.length) {
            container.innerHTML = `<div>Сейчас нет подарков от 15 ⭐.</div>`;
            return;
        }

        container.innerHTML = "";
        available.forEach((gift, idx) => {
            const price = gift.star_count || 0;
            const canAfford = gameBal >= price;
            const giftId = gift.id;
            const fallbackEmoji = gift?.sticker?.emoji || "🎁";
            const label = gift.display_name || `${fallbackEmoji} Подарок №${idx + 1}`;

            const item = document.createElement("button");
            item.disabled = !canAfford;
            item.style.cssText = `
                width: 100%; display: flex; justify-content: space-between; align-items: center;
                padding: 10px 12px; margin-bottom: 8px; border-radius: 12px;
                border: 1px solid ${canAfford ? "rgba(76,175,80,0.5)" : "rgba(255,255,255,0.08)"};
                background: ${canAfford ? "#222b38" : "#14171d"};
                color: ${canAfford ? "#fff" : "#777"};
                cursor: ${canAfford ? "pointer" : "not-allowed"}; font-size: 14px;
            `;
            item.innerHTML = `
                <span>${label}</span>
                <strong>${price} ⭐</strong>
            `;
            if (canAfford) {
                item.onclick = () => submitGiftWithdraw(giftId, price);
            }
            container.appendChild(item);
        });
    } catch (e) {
        console.error("Ошибка загрузки подарков:", e);
        container.innerHTML = `<div style="color:#ff6b6b;">Ошибка сети при загрузке подарков</div>`;
    }
}

function handleWithdraw(type) {
    const gameBal = parseInt(document.getElementById("game-balance-amount").textContent) || 0;
    const bonusBal = parseInt(document.getElementById("bonus-balance-amount").textContent) || 0;

    if (type === "game") {
        if (gameBal < 15) {
            if (tg.showAlert) tg.showAlert(`Минимальная стоимость подарка для вывода: 15 ⭐. У вас сейчас ${gameBal} ⭐.`);
            else alert(`Минимальная стоимость подарка для вывода: 15 ⭐.`);
            return;
        }
        openGiftWithdrawModal(gameBal);
    } else {
        if (bonusBal < 500) {
            if (tg.showAlert) tg.showAlert("Минимальный вывод с Бонусного баланса: 500 ⭐.");
            else alert("Минимальный вывод с Бонусного баланса: 500 ⭐.");
        } else {
            if (tg.showAlert) tg.showAlert(`Заявка на вывод ${bonusBal} ⭐ с Бонусного баланса принята!`);
            else alert(`Заявка на вывод ${bonusBal} ⭐ с Бонусного баланса принята!`);
        }
    }
}
