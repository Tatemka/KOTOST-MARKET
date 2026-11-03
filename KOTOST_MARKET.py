import event, cyberpi, time
import socket

@event.start
def on_start():
    cyberpi.console.clear()
    cyberpi.wifi.connect("ВАШ_WIFI", "ВАШ_ПАРОЛЬ")
    time.sleep(5)
    if cyberpi.wifi.is_connected():
        cyberpi.console.print("Готов!")
    else:
        cyberpi.console.print("Wi-Fi FAIL!")

@event.is_press('b')
def is_btn_press():
    cyberpi.console.print("Отправка...")
    cyberpi.audio.play('iron')
    
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(("IP_ВАШЕГО_СЕРВЕРА", 5051))
        client.send("ТОКЕН_ИЗ_kot_final.py:ЗАКАЗ КОТОСТИ".encode('utf-8'))
        cyberpi.console.print("OK!")
    except Exception as e:
        cyberpi.console.print("Err: " + str(e)) # Покажет текст ошибки
    finally:
        client.close()
