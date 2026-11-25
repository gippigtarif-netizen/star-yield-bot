const tg = window.Telegram?.WebApp || {};
if (typeof tg.ready === "function") tg.ready();
if (typeof tg.expand === "function") tg.expand();

const user = tg.initDataUnsafe?.user || {};
const userId = user.id || 123456789;
const username = user.username || "";
const firstName = user.first_name || "Игрок";

const STAR_EMOJI_REGEX = /\u2b50\ufe0f?/g;

const TG_STAR_SVG = `<svg class="tg-star-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" style="width:16px;height:16px;min-width:16px;display:inline-block;vertical-align:-2px;filter:drop-shadow(0 1px 2px rgba(245,158,11,0.45));"><path fill="#f59e0b" d="M12.82 2.45c-.34-.67-1.3-.67-1.64 0L8.27 8.35l-6.51.95c-.74.11-1.04 1.02-.5 1.54l4.71 4.59-1.11 6.48c-.13.74.65 1.3 1.31.95l5.82-3.06 5.82 3.06c.66.35 1.44-.21 1.31-.95l-1.11-6.48 4.71-4.59c.54-.52.24-1.43-.5-1.54l-6.51-.95-2.91-5.9zm2.38 8.35l-6.55 4.12 2.35 1.25 6.4-4.95-2.2-.42z"/></svg>`;

function haptic(type = "light", kind = "impact") {
    try {
        if (kind === "notification" && tg.HapticFeedback?.notificationOccurred) {
            tg.HapticFeedback.notificationOccurred(type);
        } else if (kind === "selection" && tg.HapticFeedback?.selectionChanged) {
            tg.HapticFeedback.selectionChanged();
        } else if (tg.HapticFeedback?.impactOccurred) {
            tg.HapticFeedback.impactOccurred(type);
        }
    } catch (_) {}
}

function showAlertSafe(msg) {
    if (typeof tg.showAlert === "function") {
        tg.showAlert(msg);
    } else {
        alert(msg);
    }
}

function formatStarsText(text) {
    return String(text ?? "").replace(STAR_EMOJI_REGEX, TG_STAR_SVG);
}

function hydrateStarIcons(root = document) {
    if (!root) return;
    root.querySelectorAll("[data-star-icon]").forEach(el => {
        el.innerHTML = TG_STAR_SVG;
    });
}

function replaceEmojiStarsInDom(root = document.body) {
    if (!root) return;

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    let current;
    while ((current = walker.nextNode())) {
        if (current.nodeValue && STAR_EMOJI_REGEX.test(current.nodeValue)) {
            STAR_EMOJI_REGEX.lastIndex = 0;
            const parentEl = current.parentElement;
            const parentTag = parentEl?.tagName;
            if (
                parentTag &&
                parentTag !== "SCRIPT" &&
                parentTag !== "STYLE" &&
                !parentEl.closest("button")
            ) {
                textNodes.push(current);
            }
        }
    }

    textNodes.forEach(node => {
        const parent = node.parentElement;
        if (!parent) return;
        const span = document.createElement("span");
        span.innerHTML = formatStarsText(node.nodeValue);
        parent.replaceChild(span, node);
    });
}

const TICKET_UI = {
    gray: { id: "gray", name: "Серый билет", price: 5, color: "#8e929b" },
    blue: { id: "blue", name: "Синий билет", price: 15, color: "#3b82f6" },
    burgundy: { id: "burgundy", name: "Бордовый билет", price: 35, color: "#881337" },
    purple: { id: "purple", name: "Фиолетовый билет", price: 75, color: "#9333ea" },
    gold: { id: "gold", name: "Золотой билет", price: 150, color: "#eab308" }
};

let selectedTicketId = "gray";
let currentGameBalance = 0;
let currentBonusBalance = 0;
let isOpeningTicket = false;
let isWithdrawingGift = false;
let isTransferringBonus = false;

function loadUserAvatar(avatarEl, fallbackLetter) {
    if (!avatarEl) return;

    const img = document.createElement("img");
    img.alt = "Аватар";
    img.style.width = "52px";
    img.style.height = "52px";
    img.style.objectFit = "cover";
    img.style.borderRadius = "50%";
    img.style.display = "block";
    img.src = `/api/avatar/${encodeURIComponent(userId)}?t=${Date.now()}`;

    img.onload = () => {
        avatarEl.textContent = "";
        avatarEl.appendChild(img);
    };

    img.onerror = () => {
        avatarEl.innerHTML = "";
        avatarEl.textContent = fallbackLetter;
    };
}

function removePromoBanners() {
    document.querySelectorAll(".promo-banner").forEach(el => el.remove());
    document.querySelectorAll("div, section").forEach(el => {
        if (
            el.children.length <= 2 &&
            el.textContent &&
            el.textContent.includes("Больше заданий скоро!")
        ) {
            el.remove();
        }
    });
}

function clearTicketFooterStatus() {
    const statusEl = document.getElementById("game-status");
    if (statusEl) {
        statusEl.textContent = "";
        statusEl.style.display = "none";
    }
}

function styleLastProfileButtonGreen() {
    document.querySelectorAll("button").forEach(btn => {
        if (btn.textContent && btn.textContent.includes("Вывести с Бонусного баланса")) {
            btn.style.background = "linear-gradient(135deg, #22c55e 0%, #16a34a 100%)";
            btn.style.border = "3px solid #4ade80";
            btn.style.color = "#ffffff";
            btn.style.boxShadow = "0 4px 15px rgba(34, 197, 94, 0.3)";
        }
    });
}

function renderTicketsStarsCounter(amount = currentGameBalance) {
    const safeVal = Math.max(0, Number(amount) || 0);
    currentGameBalance = safeVal;
    const el = document.getElementById("tickets-balance-count");
    if (el) {
        el.innerHTML = `<span style="display:inline-flex; align-items:center; gap:4px;">${safeVal} ${TG_STAR_SVG}</span>`;
    }
}

function applyUiFixes() {
    removePromoBanners();
    clearTicketFooterStatus();
    hydrateStarIcons(document);
    replaceEmojiStarsInDom(document.body);
    renderTicketsStarsCounter(currentGameBalance);
    styleLastProfileButtonGreen();
}

document.addEventListener("DOMContentLoaded", () => {
    const nameEl = document.getElementById("user-name");
    const avatarEl = document.getElementById("user-avatar");
    const fallbackLetter = firstName ? firstName.charAt(0).toUpperCase() : "👤";

    if (nameEl) nameEl.textContent = firstName;
    if (avatarEl) {
        avatarEl.textContent = fallbackLetter;
        loadUserAvatar(avatarEl, fallbackLetter);
    }

    backToGamesHub();
    updateTicketPreview(selectedTicketId);
    applyUiFixes();
    loadBalance(2);
});

function openSubGame(gameKey) {
    if (isOpeningTicket) return;

    const hub = document.getElementById("games-hub");
    if (hub) hub.style.display = "none";

    document.querySelectorAll('[id^="subgame-"]').forEach(el => {
        el.style.display = "none";
    });

    const target = document.getElementById(`subgame-${gameKey}`);
    if (target) target.style.display = "block";

    applyUiFixes();
    haptic("light");
}

function backToGamesHub() {
    document.querySelectorAll('[id^="subgame-"]').forEach(el => {
        el.style.display = "none";
    });

    const hub = document.getElementById("games-hub");
    if (hub) hub.style.display = "block";

    haptic("light");
}

function switchTab(tabName) {
    const tabTasks = document.getElementById("tab-tasks");
    const tabGames = document.getElementById("tab-games");
    const tabProfile = document.getElementById("tab-profile");
    const viewTasks = document.getElementById("view-tasks");
    const viewGames = document.getElementById("view-games");
    const viewProfile = document.getElementById("view-profile");

    [tabTasks, tabGames, tabProfile, viewTasks, viewGames, viewProfile].forEach(el => {
        if (el) el.classList.remove("active");
    });

    if (tabName === "tasks") {
        if (tabTasks) tabTasks.classList.add("active");
        if (viewTasks) viewTasks.classList.add("active");
    } else if (tabName === "games") {
        if (tabGames) tabGames.classList.add("active");
        if (viewGames) viewGames.classList.add("active");
        backToGamesHub();
    } else {
        if (tabProfile) tabProfile.classList.add("active");
        if (viewProfile) viewProfile.classList.add("active");
    }

    applyUiFixes();
    haptic("light");
}

function renderBalances(data) {
    if (!data) return;
    if (data.game_balance !== undefined) {
        const gameVal = Math.max(0, Number(data.game_balance) || 0);
        currentGameBalance = gameVal;
        const gameEl = document.getElementById("game-balance-amount");
        if (gameEl) gameEl.textContent = gameVal;
        renderTicketsStarsCounter(gameVal);
    }
    if (data.bonus_balance !== undefined) {
        const bonusVal = Math.max(0, Number(data.bonus_balance) || 0);
        currentBonusBalance = bonusVal;
        const bonusEl = document.getElementById("bonus-balance-amount");
        if (bonusEl) bonusEl.textContent = bonusVal;
    }
}

async function loadBalance(retries = 1) {
    try {
        const params = new URLSearchParams({ user_id: userId, username, first_name: firstName });
        const response = await fetch(`/api/get_balance?${params.toString()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        renderBalances(data);
        applyUiFixes();
    } catch (error) {
        console.error("Ошибка загрузки баланса:", error);
        if (retries > 0) {
            setTimeout(() => loadBalance(retries - 1), 1500);
        }
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
        if (response.ok && data.success) {
            renderBalances(data);
            applyUiFixes();
            haptic("success", "notification");
        } else {
            showAlertSafe(data.error || "Не удалось начислить награду");
        }
    } catch (error) {
        console.error("Ошибка:", error);
        showAlertSafe("Ошибка соединения с сервером");
    } finally {
        if (btnElement) setTimeout(() => { btnElement.disabled = false; }, 600);
    }
}

function updateTicketPreview(ticketId) {
    const info = TICKET_UI[ticketId] || TICKET_UI.gray;
    const badgeEl = document.getElementById("stage-badge");
    const titleEl = document.getElementById("stage-title");
    const openBtn = document.getElementById("open-ticket-btn");
    const stageEl = document.getElementById("ticket-stage");

    if (badgeEl) {
        badgeEl.innerHTML = `${info.name.toUpperCase()} • ${info.price} ${TG_STAR_SVG}`;
        badgeEl.style.border = `3px solid ${info.color}`;
    }
    if (titleEl && !isOpeningTicket) {
        titleEl.textContent = "Готов к открытию";
    }
    if (openBtn) {
        openBtn.innerHTML = `Открыть ${info.name} (${info.price} ${TG_STAR_SVG})`;
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
        item.style.borderColor = "rgba(255, 255, 255, 0.16)";
    });

    if (btnElement) {
        btnElement.classList.add("active");
        btnElement.style.borderColor = TICKET_UI[ticketId].color;
    }

    updateTicketPreview(ticketId);
    haptic(undefined, "selection");
}

function closeTicketShopModal() {
    const modal = document.getElementById("ticket-shop-modal");
    if (modal) modal.remove();
}

function openTicketShopModal() {
    closeTicketShopModal();
    openTopupPrompt();
}

async function openBonusTransferPrompt() {
    if (isTransferringBonus) return;

    const bonusBal = currentBonusBalance || (parseInt(document.getElementById("bonus-balance-amount")?.textContent, 10) || 0);
    if (bonusBal <= 0) {
        showAlertSafe("На Бонусном балансе пока 0 звёзд.");
        return;
    }

    const raw = prompt(
        `Перевод с Бонусного баланса на Игровой (обратный перевод невозможен).\nДоступно бонусов: ${bonusBal}`,
        String(bonusBal)
    );
    if (!raw) return;

    const amount = parseInt(raw, 10);
    if (isNaN(amount) || amount < 1 || amount > bonusBal) {
        showAlertSafe(`Введите число от 1 до ${bonusBal}`);
        return;
    }

    isTransferringBonus = true;
    try {
        const res = await fetch("/api/transfer_bonus", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, amount, username, first_name: firstName })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            renderBalances(data);
            applyUiFixes();
            haptic("success", "notification");
            showAlertSafe(`Переведено ${data.spent_bonus} бонусных -> +${data.received_game} игровых.`);
        } else {
            haptic("error", "notification");
            showAlertSafe(data.error || "Ошибка перевода бонусов");
        }
    } catch (e) {
        console.error("Ошибка перевода бонусов:", e);
        showAlertSafe("Ошибка соединения с сервером");
    } finally {
        isTransferringBonus = false;
    }
}

async function openTopupPrompt() {
    const raw = prompt("Сколько звёзд Telegram зачислить на Игровой баланс? (от 1 до 10000)", "15");
    if (!raw) return;
    const amount = parseInt(raw, 10);
    if (isNaN(amount) || amount < 1 || amount > 10000) {
        showAlertSafe("Введите корректное число от 1 до 10000");
        return;
    }

    try {
        const res = await fetch("/api/create_invoice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ amount, user_id: userId })
        });
        const data = await res.json();
        if (data.invoice_link && typeof tg.openInvoice === "function") {
            tg.openInvoice(data.invoice_link, (status) => {
                if (status === "paid") {
                    haptic("success", "notification");
                    setTimeout(() => loadBalance(2), 800);
                }
            });
        } else {
            showAlertSafe(data.error || "Ошибка создания счёта");
        }
    } catch (e) {
        console.error("Ошибка оплаты:", e);
        showAlertSafe("Ошибка соединения с сервером");
    }
}

async function openSelectedTicket() {
    if (isOpeningTicket) return;

    const ticketInfo = TICKET_UI[selectedTicketId] || TICKET_UI.gray;
    const domBal = parseInt(document.getElementById("game-balance-amount")?.textContent, 10) || 0;
    const gameBalance = Math.max(currentGameBalance, domBal);

    if (gameBalance < ticketInfo.price) {
        showAlertSafe(`Недостаточно звёзд для билета «${ticketInfo.name}» (${ticketInfo.price}).`);
        return;
    }

    isOpeningTicket = true;
    clearTicketFooterStatus();

    const openBtn = document.getElementById("open-ticket-btn");
    const stageEl = document.getElementById("ticket-stage");
    const stageTitleEl = document.getElementById("stage-title");
    const gameBalEl = document.getElementById("game-balance-amount");

    if (openBtn) openBtn.disabled = true;
    if (stageEl) stageEl.classList.add("opening");
    if (stageTitleEl) stageTitleEl.innerHTML = `Списываем ${ticketInfo.price} ${TG_STAR_SVG}...`;

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
            showAlertSafe(resultData.error || "Ошибка открытия билета");
            return;
        }
    } catch (e) {
        isOpeningTicket = false;
        if (openBtn) openBtn.disabled = false;
        if (stageEl) stageEl.classList.remove("opening");
        if (stageTitleEl) stageTitleEl.textContent = "Готов к открытию";
        showAlertSafe("Ошибка соединения с сервером");
        return;
    }

    const balanceAfterSpend = resultData.won
        ? Math.max(0, Number(resultData.game_balance) - Number(resultData.prize))
        : Number(resultData.game_balance);

    if (gameBalEl) {
        gameBalEl.textContent = balanceAfterSpend;
    }
    renderTicketsStarsCounter(balanceAfterSpend);

    if (stageTitleEl) {
        stageTitleEl.innerHTML = `Списано ${ticketInfo.price} ${TG_STAR_SVG} • Открываем...`;
    }

    haptic("medium");

    setTimeout(() => {
        isOpeningTicket = false;
        if (openBtn) openBtn.disabled = false;
        if (stageEl) stageEl.classList.remove("opening");
        renderBalances(resultData);

        const formattedLabel = formatStarsText(resultData.label);

        if (resultData.won) {
            if (stageTitleEl) stageTitleEl.innerHTML = `Начислено +${resultData.prize} ${TG_STAR_SVG} (${formattedLabel})`;
            haptic("success", "notification");
        } else {
            if (stageTitleEl) stageTitleEl.textContent = "Пусто";
            haptic("error", "notification");
        }
        applyUiFixes();
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

        if (res.ok && data.success) {
            renderBalances(data);
            applyUiFixes();
            closeGiftModal();
            haptic("success", "notification");
            showAlertSafe(data.message || `Подарок за ${amount} отправлен!`);
        } else {
            haptic("error", "notification");
            showAlertSafe(data.error || "Ошибка вывода подарка");
        }
    } catch (e) {
        console.error("Ошибка вывода:", e);
        showAlertSafe("Ошибка соединения с сервером");
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
        border: 3px solid rgba(255,255,255,0.14);
    `;

    box.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <div style="font-weight:700; font-size:16px; display:inline-flex; align-items:center; gap:6px;">🎁 Вывод подарком (${gameBal} ${TG_STAR_SVG})</div>
            <button id="close-gift-modal-btn" style="background:#2a303c; color:#fff; border:3px solid rgba(255,255,255,0.18); border-radius:8px; padding:4px 10px; cursor:pointer;">✕</button>
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
            container.innerHTML = `<div>Сейчас нет подарков от 15 ${TG_STAR_SVG}.</div>`;
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
                border: 3px solid ${canAfford ? "rgba(76,175,80,0.6)" : "rgba(255,255,255,0.1)"};
                background: ${canAfford ? "#222b38" : "#14171d"};
                color: ${canAfford ? "#fff" : "#777"};
                cursor: ${canAfford ? "pointer" : "not-allowed"}; font-size: 14px;
            `;
            item.innerHTML = `
                <span>${label}</span>
                <strong style="display:inline-flex; align-items:center; gap:4px;">${price} ${TG_STAR_SVG}</strong>
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
    const gameBal = currentGameBalance || (parseInt(document.getElementById("game-balance-amount")?.textContent, 10) || 0);
    const bonusBal = currentBonusBalance || (parseInt(document.getElementById("bonus-balance-amount")?.textContent, 10) || 0);

    if (type === "game") {
        if (gameBal < 15) {
            showAlertSafe(`Минимальная стоимость подарка для вывода: 15. У вас сейчас ${gameBal}.`);
            return;
        }
        openGiftWithdrawModal(gameBal);
    } else {
        if (bonusBal < 500) {
            showAlertSafe("Минимальный вывод с Бонусного баланса: 500.");
        } else {
            showAlertSafe(`Заявка на вывод ${bonusBal} с Бонусного баланса принята!`);
        }
    }
}
