from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import sqlite3
import requests
import urllib.parse
import time
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'ВАШ_ТОКЕН_ИЗ_kot_final.py' # Секретный ключ для сессий

NTFY_URL = "IP_ВАШЕГО_СЕРВЕРА/kotost-market"
DB_PATH = "/home/dietpi/kotost.db"

# === ЗАЩИТА ОТ DDOS ===
ip_timestamps = {}
MAX_REQUESTS_PER_MINUTE = 10

def is_rate_limited(ip):
    now = time.time()
    if ip not in ip_timestamps:
        ip_timestamps[ip] = []
    ip_timestamps[ip] = [t for t in ip_timestamps[ip] if now - t < 60]
    if len(ip_timestamps[ip]) >= MAX_REQUESTS_PER_MINUTE:
        return True
    ip_timestamps[ip].append(now)
    return False

# === БАЗА ДАННЫХ ===
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Таблица заказов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT,
        ip_address TEXT,
        order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Таблица пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# === HTML-ШАБЛОНЫ ===
BASE_STYLE = """
<style>
    body { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; display: flex; justify-content: center; }
    .container { width: 100%; max-width: 900px; }
    h1 { color: #4d6bfe; text-align: center; font-size: 2.5rem; margin-bottom: 5px; text-shadow: 0 0 10px rgba(77, 107, 254, 0.3); }
    .subtitle { text-align: center; color: #a0a0a0; margin-bottom: 30px; font-size: 1.1rem; }
    .card { background-color: #1e1e1e; border-radius: 12px; padding: 20px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5); border: 1px solid #333; margin-bottom: 20px; }
    table { width: 100%; border-collapse: collapse; }
    th { text-align: left; padding: 12px 15px; background-color: #2d2d2d; color: #fff; font-weight: 600; border-bottom: 2px solid #4d6bfe; }
    td { padding: 12px 15px; border-bottom: 1px solid #333; color: #b0b0b0; }
    tr:hover td { background-color: #252525; color: #fff; }
    .order-text { color: #ffaa00; font-weight: bold; }
    .stats { margin-top: 20px; padding: 15px; background-color: #1e1e1e; border-radius: 12px; text-align: center; font-size: 1.2rem; border: 1px solid #333; }
    .stats span { color: #4d6bfe; font-weight: bold; font-size: 1.4rem; }
    .btn-group { display: flex; gap: 15px; justify-content: center; margin-top: 20px; flex-wrap: wrap; }
    .btn { display: inline-block; padding: 12px 24px; background-color: #4d6bfe; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; border: none; cursor: pointer; font-size: 1rem; }
    .btn:hover { background-color: #3b53cc; }
    .btn-order { background-color: #ffaa00; color: #121212; }
    .btn-clear { background-color: #ff4444; }
    .form-input { width: 100%; padding: 10px; margin-bottom: 15px; background: #2d2d2d; border: 1px solid #444; color: white; border-radius: 8px; box-sizing: border-box; }
    .error { color: #ff4444; text-align: center; margin-bottom: 15px; }
</style>
"""

HTML_INDEX = BASE_STYLE + """
<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>🐱 КОТОСТЬ МАРКЕТ</title></head>
<body>
    <div class="container">
        <h1>🐱 КОТОСТЬ МАРКЕТ</h1>
        <div class="subtitle">Добро пожаловать, {{ username }}!</div>
        
        <div class="card">
            <table>
                <thead><tr><th>ID</th><th>Заказ</th><th>IP-адрес</th><th>Время</th></tr></thead>
                <tbody>
                    {% for order in orders %}
                    <tr>
                        <td>#{{ order[0] }}</td>
                        <td class="order-text">{{ order[1] }}</td>
                        <td>{{ order[2] }}</td>
                        <td>{{ order[3] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="stats">Всего заказов: <span>{{ orders|length }}</span></div>
        
        <div class="btn-group">
            <a href="/" class="btn">🔄 Обновить</a>
            <form action="/order" method="POST" style="margin: 0;">
                <button type="submit" class="btn btn-order">🛒 Заказать котость!</button>
            </form>
            <form action="/clear" method="POST" style="margin: 0;">
                <button type="submit" class="btn btn-clear" onclick="return confirm('Точно очистить базу?');">🗑️ Очистить</button>
            </form>
            <a href="/logout" class="btn">🚪 Выйти</a>
        </div>
    </div>
</body>
</html>
"""

HTML_LOGIN = BASE_STYLE + """
<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>Вход</title></head>
<body>
    <div class="container">
        <h1>🐱 Вход</h1>
        <div class="card" style="max-width: 400px; margin: 0 auto;">
            {% if error %}<div class="error">{{ error }}</div>{% endif %}
            <form method="POST">
                <input type="text" name="username" placeholder="Логин" class="form-input" required>
                <input type="password" name="password" placeholder="Пароль" class="form-input" required>
                <button type="submit" class="btn" style="width: 100%;">Войти</button>
            </form>
            <p style="text-align: center; margin-top: 15px;">
                Нет аккаунта? <a href="/register" style="color: #4d6bfe;">Зарегистрироваться</a>
            </p>
        </div>
    </div>
</body>
</html>
"""

HTML_REGISTER = BASE_STYLE + """
<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>Регистрация</title></head>
<body>
    <div class="container">
        <h1>🐱 Регистрация</h1>
        <div class="card" style="max-width: 400px; margin: 0 auto;">
            {% if error %}<div class="error">{{ error }}</div>{% endif %}
            <form method="POST">
                <input type="text" name="username" placeholder="Придумайте логин" class="form-input" required>
                <input type="password" name="password" placeholder="Придумайте пароль" class="form-input" required>
                <button type="submit" class="btn" style="width: 100%;">Создать аккаунт</button>
            </form>
            <p style="text-align: center; margin-top: 15px;">
                Уже есть аккаунт? <a href="/login" style="color: #4d6bfe;">Войти</a>
            </p>
        </div>
    </div>
</body>
</html>
"""

# === МАРШРУТЫ ===
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = cursor.fetchall()
    conn.close()
    return render_template_string(HTML_INDEX, orders=orders, username=session['username'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Хешируем пароль (безопасность)
            hashed_password = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template_string(HTML_REGISTER, error="Этот логин уже занят!")
        finally:
            conn.close()
            
    return render_template_string(HTML_REGISTER)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template_string(HTML_LOGIN, error="Неверный логин или пароль")
            
    return render_template_string(HTML_LOGIN)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/order', methods=['POST'])
def make_order():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    ip = request.remote_addr
    if is_rate_limited(ip):
        return "Слишком много запросов. Попробуйте позже.", 429

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders")
    count = cursor.fetchone()[0]

    if count >= 20:
        cursor.execute("DELETE FROM orders")
    
    # Записываем, кто сделал заказ
    cursor.execute("INSERT INTO orders (message, ip_address) VALUES (?, ?)", (f"ЗАКАЗ ОТ {session['username']}", ip))
    conn.commit()
    conn.close()

    try:
        safe_title = urllib.parse.quote("КОТОСТЬ МАРКЕТ")
        requests.post(
            f"{NTFY_URL}?title={safe_title}",
            data=f"ЗАКАЗ ОТ {session['username']}".encode('utf-8'),
            headers={"Priority": "high", "Tags": "cat", "Content-Type": "text/plain; charset=utf-8"},
            timeout=2
        )
    except: pass

    return redirect(url_for('index'))

@app.route('/clear', methods=['POST'])
def clear_orders():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders")
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
