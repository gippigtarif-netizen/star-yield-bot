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

async function loadBalance() {
    try {
        const params = new URLSearchParams({ user_id: userId, username, first_name: firstName });
        const response = await fetch(`/api/get_balance?${params.toString()}`);
        const data = await response.json();
        if (data.balance !== undefined) {
            document.getElementById("balance-amount").textContent = data.balance;
        }
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
            document.getElementById("balance-amount").textContent = data.balance;
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        }
    } catch (error) {
        console.error("Ошибка:", error);
    } finally {
        if (btnElement) setTimeout(() => btnElement.disabled = false, 600);
    }
}

function selectBet(amount, btnElement) {
    if (isSpinning) return;
    currentBet = amount;
    document.querySelectorAll(".bet-btn").forEach(btn => btn.classList.remove("active"));
    btnElement.classList.add("active");
    if (tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
}

async function spinWheel() {
    if (isSpinning) return;

    const currentBalance = parseInt(document.getElementById("balance-amount").textContent) || 0;
    if (currentBalance < currentBet) {
        if (tg.showAlert) tg.showAlert("Недостаточно звёзд для ставки!");
        else alert("Недостаточно звёзд!");
        return;
    }

    isSpinning = true;
    const spinBtn = document.getElementById("spin-btn");
    const statusEl = document.getElementById("game-status");
    const wheel = document.getElementById("fortune-wheel");

    spinBtn.disabled = true;
    statusEl.textContent = "Колесо крутится...";

    // Сначала списываем ставку (отправляем отрицательное значение через /api/add_reward)
    try {
        await fetch("/api/add_reward", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, reward: -currentBet, username, first_name: firstName })
        });
    } catch (e) {
        console.error(e);
    }

    // Определяем победу по шансу 0.1% (0.001)
    const isWin = Math.random() < 0.001;

    // Рассчитываем вращение (рандомные полные обороты + смещение)
    const extraSpins = 360 * 5; 
    // Если выигрыш — останавливаем на первом секторе (0-40 градус), если проигрыш — на остальных секторах
    const targetDeg = isWin ? 20 : 100 + Math.floor(Math.random() * 200);
    
    currentRotation += extraSpins + targetDeg;
    wheel.style.transform = `rotate(${currentRotation}deg)`;

    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred("medium");
    }

    setTimeout(async () => {
        isSpinning.disabled = false;
        isSpinning = false;
        spinBtn.disabled = false;

        if (isWin) {
            const prize = currentBet * 2;
            statusEl.textContent = `🎉 ПОБЕДА! Вы выиграли ${prize} ⭐!`;
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");

            // Начисляем х2 на баланс
            try {
                const response = await fetch("/api/add_reward", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_id: userId, reward: prize, username, first_name: firstName })
                });
                const data = await response.json();
                if (data.success) {
                    document.getElementById("balance-amount").textContent = data.balance;
                }
            } catch (e) {
                console.error(e);
            }
        } else {
            statusEl.textContent = `😢 Не повезло! Ставка ${currentBet} ⭐ сгорела. Попробуй еще раз!`;
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
            loadBalance();
        }
    }, 4000);
}

function handleWithdraw() {
    if (tg.showAlert) tg.showAlert("Минимальная сумма для вывода: 500 ⭐.");
    else alert("Минимальная сумма для вывода: 500 ⭐");
}

function handlePromote() {
    if (tg.showAlert) tg.showAlert("Раздел для рекламодателей скоро откроется!");
    else alert("Раздел для рекламодателей скоро откроется!");
}
