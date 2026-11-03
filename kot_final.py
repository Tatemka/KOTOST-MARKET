import socket
import requests
import threading
import time
import urllib.parse
import sqlite3

# === НАСТРОЙКИ ===
PORT_CYBERPI = 5051
PORT_OLD = 5050
NTFY_URL = "http://ВАШ СЕРВЕР/kotost-market" 
DB_PATH = "/home/dietpi/kotost.db"

# === СЕКРЕТНЫЙ ТОКЕН (придумай свой!) ===
SECRET_TOKEN = "ВАШ_ТОКЕН"

# === БАЗА ДАННЫХ (с WAL) ===
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT,
        ip_address TEXT,
        order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    return conn

db_conn = init_db()

# === ОТПРАВКА УВЕДОМЛЕНИЙ ===
def send_notification(title, message):
    try:
        safe_title = urllib.parse.quote(title)
        response = requests.post(
            f"{NTFY_URL}?title={safe_title}",
            data=message.encode('utf-8'),
            headers={"Priority": "high", "Tags": "cat", "Content-Type": "text/plain; charset=utf-8"},
            timeout=5
        )
        if response.status_code == 200:
            print(f"[{time.strftime('%H:%M:%S')}] Уведомление отправлено: {message}")
    except Exception as e:
        print(f"[ОШИБКА NTFY] {e}")

# === ОБРАБОТКА КЛИЕНТА ===
def handle_client(conn, addr):
    print(f"[+] Подключение от {addr}")
    try:
        data = conn.recv(1024).decode('utf-8').strip()
        if data:
            # === ПРОВЕРКА ТОКЕНА ===
            if not data.startswith(SECRET_TOKEN + ":"):
                print(f"[!] ОТКАЗАНО: Неверный токен от {addr[0]}. Данные: {data[:20]}...")
                conn.sendall(b"ERROR: INVALID_TOKEN\n")
                return
            
            # Отрезаем токен, получаем чистый текст заказа
            order_text = data.replace(SECRET_TOKEN + ":", "")
            print(f"[{time.strftime('%H:%M:%S')}] Получено: {order_text}")
            
            send_notification("КОТОСТЬ МАРКЕТ", order_text)
            
            try:
                conn_db = sqlite3.connect(DB_PATH, timeout=10)
                conn_db.execute('PRAGMA journal_mode=WAL;')
                cursor = conn_db.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM orders")
                count = cursor.fetchone()[0]
                
                if count >= 20:
                    cursor.execute("DELETE FROM orders")
                    print(f"[БД] Лимит 20 достигнут. База очищена!")
                
                cursor.execute("INSERT INTO orders (message, ip_address) VALUES (?, ?)", (order_text, addr[0]))
                conn_db.commit()
                conn_db.close()
                print(f"[БД] Заказ сохранён.")
            except Exception as db_err:
                print(f"[ОШИБКА БД] {db_err}")

        conn.sendall(b"OK\n")
    except Exception as e:
        print(f"[ОШИБКА] {e}")
    finally:
        conn.close()

# === ЗАПУСК СЕРВЕРА ===
def run_server(port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(5)
    print(f"[✓] Сервер слушает порт {port}")
    
    while True:
        try:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except Exception as e:
            print(f"[ОШИБКА СЕРВЕРА] {e}")

if __name__ == "__main__":
    print(f"[✓] Уведомления идут на {NTFY_URL}")
    print(f"[✓] Токен для CyberPi: {SECRET_TOKEN}")
    threading.Thread(target=run_server, args=(PORT_CYBERPI,), daemon=True).start()
    threading.Thread(target=run_server, args=(PORT_OLD,), daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Остановка сервера...")
