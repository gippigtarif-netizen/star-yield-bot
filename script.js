const tg = window.Telegram.WebApp;
tg.expand();

let userId = 12345678; // Дефолтный ID для теста в браузере
let userFirstName = "Гость";

if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
    userId = tg.initDataUnsafe.user.id;
    userFirstName = tg.initDataUnsafe.user.first_name || "Пользователь";
}

document.getElementById('username').innerText = userFirstName;
document.getElementById('user-id').innerText = userId;

// Загружаем реальный баланс из базы данных при открытии
async function fetchBalance() {
    try {
        const response = await fetch(`/api/get_balance?user_id=${userId}`);
        const data = await response.json();
        if (data.balance !== undefined) {
            document.getElementById('balance-val').innerText = data.balance;
        }
    } catch (e) {
        console.error("Ошибка загрузки баланса:", e);
    }
}

fetchBalance();

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    if (tabName === 'tasks') {
        document.querySelectorAll('.tab-btn')[0].classList.add('active');
        document.getElementById('tab-tasks').classList.add('active');
    } else {
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
        document.getElementById('tab-profile').classList.add('active');
    }
}

// Отправляем награду на сервер при выполнении задания
async function completeTask(btn, reward) {
    try {
        const response = await fetch('/api/add_reward', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, reward: reward })
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

function openPromoModal() {
    tg.HapticFeedback.notificationOccurred('warning');
    alert('Раздел покупки продвижения находится в разработке! Скоро здесь можно будет запустить рекламу своего канала.');
}
