const tg = window.Telegram.WebApp;
tg.expand();

let userId = 12345678;
let userFirstName = "Гость";
let userUsername = "";

if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
    userId = tg.initDataUnsafe.user.id;
    userFirstName = tg.initDataUnsafe.user.first_name || "Пользователь";
    userUsername = tg.initDataUnsafe.user.username || "";
}

document.getElementById('username').innerText = userFirstName;
document.getElementById('user-id').innerText = userId;

// Загружаем баланс с передачей данных пользователя
async function fetchBalance() {
    try {
        const response = await fetch(`/api/get_balance?user_id=${userId}&username=${encodeURIComponent(userUsername)}&first_name=${encodeURIComponent(userFirstName)}`);
        const data = await response.json();
        if (data.balance !== undefined) {
            document.getElementById('balance-val').innerText = data.balance;
        }
    } catch (e) {
        console.error("Ошибка загрузки баланса:", e);
    }
}

fetchBalance();

async function completeTask(btn, reward) {
    try {
        const response = await fetch('/api/add_reward', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_id: userId, 
                reward: reward,
                username: userUsername,
                first_name: userFirstName
            })
        });
        
        const data = await response.json();
        if (data.success) {
            document.getElementById('balance-val').innerText = data.balance;
            btn.disabled = true;
            btn.innerText = "Выполнено";
            btn.style.background = "#4ce666";
            tg.HapticFeedback.notificationOccurred('success');
        }
    } catch (e) {
        console.error("Ошибка сохранения задания:", e);
        alert("Не удалось сохранить награду, проверь соединение.");
    }
}
