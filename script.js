const tg = window.Telegram.WebApp;
tg.expand();

if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
    const user = tg.initDataUnsafe.user;
    document.getElementById('username').innerText = user.first_name || "Пользователь";
    document.getElementById('user-id').innerText = user.id;
} else {
    document.getElementById('username').innerText = "Гость";
    document.getElementById('user-id').innerText = "12345678";
}

let balance = 0;

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

function completeTask(btn, reward) {
    balance += reward;
    document.getElementById('balance-val').innerText = balance;
    btn.disabled = true;
    btn.innerText = "Выполнено";
    btn.style.background = "#4ce666";
    tg.HapticFeedback.notificationOccurred('success');
}

function openPromoModal() {
    tg.HapticFeedback.notificationOccurred('warning');
    alert('Раздел покупки продвижения находится в разработке! Скоро здесь можно будет запустить рекламу своего канала.');
}
