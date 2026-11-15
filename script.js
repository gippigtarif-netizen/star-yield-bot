const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// Получаем данные пользователя из Telegram
const user = tg.initDataUnsafe?.user || {};
const userId = user.id || 123456789;
const username = user.username || "";
const firstName = user.first_name || "Игрок";

// Отображаем имя в профиле и первую букву на аватарке
document.addEventListener("DOMContentLoaded", () => {
    const nameEl = document.getElementById("user-name");
    const avatarEl = document.getElementById("user-avatar");

    if (nameEl) nameEl.textContent = firstName;
    if (avatarEl && firstName) {
        avatarEl.textContent = firstName.charAt(0).toUpperCase();
    }

    loadBalance();
});

// Переключение вкладок (Задания / Профиль)
function switchTab(tabName) {
    const tabTasks = document.getElementById("tab-tasks");
    const tabProfile = document.getElementById("tab-profile");
    const viewTasks = document.getElementById("view-tasks");
    const viewProfile = document.getElementById("view-profile");

    if (tabName === "tasks") {
        tabTasks.classList.add("active");
        tabProfile.classList.remove("active");
        viewTasks.classList.add("active");
        viewProfile.classList.remove("active");
    } else {
        tabProfile.classList.add("active");
        tabTasks.classList.remove("active");
        viewProfile.classList.add("active");
        viewTasks.classList.remove("active");
    }

    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred("light");
    }
}

// Загрузка баланса с сервера
async function loadBalance() {
    try {
        const params = new URLSearchParams({
            user_id: userId,
            username: username,
            first_name: firstName
        });
        const response = await fetch(`/api/get_balance?${params.toString()}`);
        const data = await response.json();

        if (data.balance !== undefined) {
            document.getElementById("balance-amount").textContent = data.balance;
        }
    } catch (error) {
        console.error("Ошибка загрузки баланса:", error);
    }
}

// Выполнение задания и начисление награды
async function completeTask(reward, btnElement) {
    if (btnElement) btnElement.disabled = true;

    try {
        const response = await fetch("/api/add_reward", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: userId,
                reward: reward,
                username: username,
                first_name: firstName
            })
        });

        const data = await response.json();
        if (data.success) {
            document.getElementById("balance-amount").textContent = data.balance;
            if (tg.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred("success");
            }
        }
    } catch (error) {
        console.error("Ошибка начисления награды:", error);
    } finally {
        if (btnElement) {
            setTimeout(() => {
                btnElement.disabled = false;
            }, 600);
        }
    }
}

// Кнопка Вывод
function handleWithdraw() {
    if (tg.showAlert) {
        tg.showAlert("Минимальная сумма для вывода: 500 ⭐. Продолжайте выполнять задания!");
    } else {
        alert("Минимальная сумма для вывода: 500 ⭐");
    }
}

// Кнопка Продвижение
function handlePromote() {
    if (tg.showAlert) {
        tg.showAlert("Раздел для рекламодателей скоро откроется!");
    } else {
        alert("Раздел для рекламодателей скоро откроется!");
    }
}
