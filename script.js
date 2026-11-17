const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const user = tg.initDataUnsafe?.user || {};
const userId = user.id || 123456789;
const username = user.username || "";
const firstName = user.first_name || "Игрок";

let currentBet = 5;
let currentRotation = 0;
let isSpinning = false;

document.addEventListener("DOMContentLoaded", () => {
    const nameEl = document.getElementById("user-name");
    const avatarEl = document.getElementById("user-avatar");

    if (nameEl) nameEl.textContent = firstName;
    if (avatarEl && firstName) {
        avatarEl.textContent = firstName.charAt(0).toUpperCase();
    }

    updateBetPreview(currentBet);
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

// Формула отображения шанса на клиенте
function updateBetPreview(amount) {
    const winLabel = document.getElementById("potential-win-label");
    const chanceLabel = document.getElementById("win-chance-label");

    if (!amount || amount < 1) {
        if (winLabel) winLabel.textContent = "0 ⭐";
        if (chanceLabel) chanceLabel.textContent = "0%";
        return;
    }

    const clamped = Math.min(amount, 1000);
    const chance = Math.min(0.999 * Math.pow(clamped / 1000, 0.7), 0.999);

    if (winLabel) winLabel.textContent = `${clamped * 2} ⭐`;
    if (chanceLabel) chanceLabel.textContent = `${chance.toFixed(3)}%`;
}

function selectBet(amount, btnElement) {
    if (isSpinning) return;
    currentBet = amount;
    const input = document.getElementById("custom-bet-input");
    if (input) input.value = amount;

    document.querySelectorAll(".bet-btn").forEach(btn => btn.classList.remove("active"));
    if (btnElement) btnElement.classList.add("active");

    updateBetPreview(amount);
    if (tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
}

function onCustomBetInput(rawValue) {
    if (isSpinning) return;
    document.querySelectorAll(".bet-btn").forEach(btn => btn.classList.remove("active"));

    let val = parseInt(rawValue, 10);
    if (isNaN(val)) {
        currentBet = 0;
        updateBetPreview(0);
        return;
    }
    if (val > 1000) {
        val = 1000;
        document.getElementById("custom-bet-input").value = 1000;
    }
    currentBet = val;
    updateBetPreview(val);
}

async function openTopupPrompt() {
    const raw = prompt("Сколько звёзд Telegram (⭐) зачислить на Игровой баланс? (от 1 до 10000)", "1");
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
                    loadBalance();
                }
            });
        } else {
            if (tg.showAlert) tg.showAlert(data.error || "Ошибка создания счёта");
        }
    } catch (e) {
        console.error("Ошибка оплаты:", e);
    }
}

async function spinWheel() {
    if (isSpinning) return;

    if (!currentBet || currentBet < 1 || currentBet > 1000) {
        if (tg.showAlert) tg.showAlert("Введите ставку от 1 до 1000 ⭐!");
        else alert("Введите ставку от 1 до 1000 ⭐!");
        return;
    }

    const gameBalance = parseInt(document.getElementById("game-balance-amount").textContent) || 0;
    if (gameBalance < currentBet) {
        if (tg.showAlert) tg.showAlert("Недостаточно звёзд на Игровом балансе! Нажмите «+ Пополнить».");
        else alert("Недостаточно звёзд на Игровом балансе!");
        return;
    }

    isSpinning = true;
    const spinBtn = document.getElementById("spin-btn");
    const statusEl = document.getElementById("game-status");
    const wheel = document.getElementById("fortune-wheel");

    spinBtn.disabled = true;
    statusEl.textContent = "Колесо крутится...";

    let spinResult = null;
    try {
        const res = await fetch("/api/spin_wheel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: userId,
                bet: currentBet,
                username,
                first_name: firstName
            })
        });
        spinResult = await res.json();

        if (!res.ok || !spinResult.success) {
            isSpinning = false;
            spinBtn.disabled = false;
            statusEl.textContent = spinResult.error || "Ошибка ставки";
            if (tg.showAlert) tg.showAlert(spinResult.error || "Ошибка ставки");
            return;
        }
    } catch (e) {
        isSpinning = false;
        spinBtn.disabled = false;
        statusEl.textContent = "Ошибка соединения с сервером";
        return;
    }

    const displayDuringSpin = spinResult.won
        ? spinResult.game_balance - spinResult.prize
        : spinResult.game_balance;
    document.getElementById("game-balance-amount").textContent = Math.max(0, displayDuringSpin);

    const isWin = spinResult.won;
    const desiredFinalAngle = isWin
        ? 342
        : 20 + Math.floor(Math.random() * 290);

    const currentMod = currentRotation % 360;
    let deltaAngle = desiredFinalAngle - currentMod;
    if (deltaAngle < 0) deltaAngle += 360;

    currentRotation += (360 * 5) + deltaAngle;
    wheel.style.transform = `rotate(${currentRotation}deg)`;

    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred("medium");
    }

    setTimeout(() => {
        isSpinning = false;
        spinBtn.disabled = false;
        renderBalances(spinResult);

        if (isWin) {
            statusEl.textContent = `🎉 ПОБЕДА! Вы выиграли ${spinResult.prize} ⭐!`;
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        } else {
            statusEl.textContent = `😢 Не повезло! Ставка ${currentBet} ⭐ сгорела. Попробуй еще раз!`;
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
        }
    }, 4000);
}

function handleWithdraw(type) {
    const gameBal = parseInt(document.getElementById("game-balance-amount").textContent) || 0;
    const bonusBal = parseInt(document.getElementById("bonus-balance-amount").textContent) || 0;

    if (type === "game") {
        if (gameBal < 1) {
            if (tg.showAlert) tg.showAlert("На Игровом балансе нет звёзд для вывода.");
        } else {
            if (tg.showAlert) tg.showAlert(`Заявка на вывод ${gameBal} ⭐ с Игрового баланса принята!`);
        }
    } else {
        if (bonusBal < 500) {
            if (tg.showAlert) tg.showAlert("Минимальный вывод с Бонусного баланса: 500 ⭐.");
        } else {
            if (tg.showAlert) tg.showAlert(`Заявка на вывод ${bonusBal} ⭐ с Бонусного баланса принята!`);
        }
    }
}
