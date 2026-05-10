from customtkinter import *
from PIL import Image, ImageDraw, ImageFont
import threading
from socket import socket, AF_INET, SOCK_STREAM
import time
import json, os
import base64, io
from tkinter import filedialog

set_appearance_mode("light")

app = CTk()
app.title("LogiTalk")
app.geometry("900x500")
app.resizable(False, False)

HOST = "7.tcp.eu.ngrok.io"
PORT = 25057

sock = None
connected = False
my_name = ""

# ─── NETWORK ─────────────────────────────────────────

def send_msg(event=None):
    message = msg_input.get().strip()
    if message and sock:
        try:
            payload = f"TEXT@{my_name}@{message}\n"
            sock.sendall(payload.encode("utf-8"))

            msg_input.delete(0, END)
            app.after(0, lambda: add_bubble(my_name, message, own=True))
        except Exception as e:
            print("Send error:", e)


def send_image():
    if not sock:
        return

    file_name = filedialog.askopenfilename()
    if not file_name:
        return

    try:
        with open(file_name, "rb") as f:
            raw = f.read()

        b64 = base64.b64encode(raw).decode()
        short_name = os.path.basename(file_name)

        data = f"IMAGE@{my_name}@{short_name}@{b64}\n"
        sock.sendall(data.encode())

        img = Image.open(file_name)
        ctk_img = CTkImage(light_image=img, size=(250, 250))

        add_bubble(my_name, f"[Фото] {short_name}", True, ctk_img)

    except Exception as e:
        print("Image send error:", e)


def recv_message():
    global connected
    buffer = ""

    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break

            buffer += chunk.decode("utf-8", errors="ignore")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()

                if line:
                    app.after(0, lambda l=line: parse_and_display(l))

        except Exception as e:
            print("Recv error:", e)
            break

    connected = False


def parse_and_display(raw):
    parts = raw.split("@", 3)

    if parts[0] == "TEXT" and len(parts) >= 3:
        sender, text = parts[1], parts[2]

        if sender != my_name:
            add_bubble(sender, text, False)

    elif parts[0] == "IMAGE" and len(parts) >= 4:
        sender, filename, b64 = parts[1], parts[2], parts[3]

        try:
            img_data = base64.b64decode(b64)
            pil_img = Image.open(io.BytesIO(img_data))
            ctk_img = CTkImage(light_image=pil_img, size=(250, 250))

            add_bubble(sender, f"[Фото] {filename}", False, ctk_img)
        except Exception as e:
            add_system_msg(f"Помилка зображення: {e}")

    else:
        add_system_msg(raw)


def connect_to_server(username):
    global sock, connected, my_name

    my_name = username

    try:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect((HOST, PORT))

        connected = True
        save_to_history(username, HOST, PORT)

        hello = f"TEXT@{username}@[SYSTEM] {username} приєднався!\n"
        sock.sendall(hello.encode("utf-8"))

        draw_chat_gui()

        app.after(100, lambda: add_system_msg(f"✓ Підключено до {HOST}:{PORT}"))

        threading.Thread(target=recv_message, daemon=True).start()

    except Exception as e:
        connected = False
        status_label.configure(text=f"Помилка: {e}", text_color="#e74c3c")

# ─── UI (ТВОЙ ОРИГИНАЛ + МАЛЕНЬКОЕ ДОБАВЛЕНИЕ КНОПКИ 📎) ─────────────

chat_scroll = None
msg_input = None

def draw_chat_gui():
    global chat_scroll, msg_input

    for widget in app.winfo_children():
        widget.destroy()

    app.geometry("980x640")
    app.resizable(True, True)

    root_frame = CTkFrame(app, fg_color="#f0f2f5")
    root_frame.pack(fill="both", expand=True)

    sidebar = CTkFrame(root_frame, width=220, fg_color="#ffffff")
    sidebar.pack(side="left", fill="y")

    CTkLabel(sidebar, text="LogiTalk", font=("Arial", 22, "bold"),
             text_color="#d16ba5").pack(pady=(28, 6), padx=20, anchor="w")

    chat_area = CTkFrame(root_frame, fg_color="#f7f8fa")
    chat_area.pack(side="right", fill="both", expand=True)

    chat_scroll = CTkScrollableFrame(chat_area)
    chat_scroll.pack(fill="both", expand=True)

    add_system_msg(f"Ласкаво просимо до LogiTalk, {my_name}!")

    input_bar = CTkFrame(chat_area)
    input_bar.pack(fill="x", side="bottom")

    inner = CTkFrame(input_bar)
    inner.pack(fill="x", padx=10, pady=10)

    msg_input = CTkEntry(inner)
    msg_input.pack(side="left", fill="x", expand=True)
    msg_input.bind("<Return>", send_msg)

    CTkButton(inner, text="📎", width=40, command=send_image).pack(side="left", padx=5)
    CTkButton(inner, text="➤", width=40, command=send_msg).pack(side="right")

# ─── BUBBLES ─────────────────────────────────────────

def add_bubble(sender, text, own=False, img=None):
    if chat_scroll is None:
        return

    frame = CTkFrame(chat_scroll)
    frame.pack(anchor="e" if own else "w", pady=5, padx=10)

    if img:
        CTkLabel(frame, text=text, image=img, compound="top").pack(padx=10, pady=5)
    else:
        CTkLabel(frame, text=f"{sender}: {text}").pack(padx=10, pady=5)

    app.after(50, lambda: chat_scroll._parent_canvas.yview_moveto(1.0))


def add_system_msg(text):
    if chat_scroll is None:
        return
    CTkLabel(chat_scroll, text=text, text_color="#aaa").pack(pady=6)

# ─── HISTORY ─────────────────────────────────────────

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")

def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_to_history(username, host, port):
    history = load_history()
    entry = {"user": username, "host": host, "port": port,
             "time": time.strftime("%d.%m.%Y %H:%M")}
    if not history or history[0] != entry:
        history.insert(0, entry)
    history = history[:20]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except:
        pass

# ─── LOGIN ─────────────────────────────────────────

def on_login():
    u = name.get().strip()

    if not u:
        status_label.configure(text="Введіть нікнейм")
        return

    status_label.configure(text="З'єднання...")
    app.update()

    connect_to_server(u)

name = CTkEntry(app, placeholder_text="Нікнейм")
name.pack(pady=20)

login = CTkButton(app, text="УВІЙТИ", command=on_login)
login.pack(pady=10)

status_label = CTkLabel(app, text="")
status_label.pack()

app.mainloop()