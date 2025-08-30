import logging
import sys
import traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import time
import re
import os
import json
import configparser
import requests

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None

APP_NAME = "GhostMonitorLOG"
CONFIG_INI_PATH = "config/default_messages.ini"
CONFIG_JSON_PATH = "data/settings.json"

logging.basicConfig(
    filename="app.log",
    filemode="a",
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.DEBUG
)

def log_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception",
                  exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = log_exception

class ConfigWatcher:
    def __init__(self, filepath):
        self.filepath = filepath
        self.last_mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else 0
        self.config = self.load_config()
        logging.info(f"ConfigWatcher iniciado con archivo: {filepath}")

    def load_config(self):
        config = configparser.ConfigParser()
        config.read(self.filepath, encoding="utf-8")
        if "MESSAGES" not in config:
            config["MESSAGES"] = {}
        return config

    def check_for_changes(self):
        if os.path.exists(self.filepath):
            current_mtime = os.path.getmtime(self.filepath)
            if current_mtime != self.last_mtime:
                self.last_mtime = current_mtime
                self.config = self.load_config()
                logging.info(f"{APP_NAME}: Config messages updated")
                return True
        return False

class MonitorThread(threading.Thread):
    def __init__(self, log_path, webhook, config_watcher, stop_event, output_callback=None):
        super().__init__(daemon=True)
        self.log_path = log_path
        self.webhook = webhook
        self.config_watcher = config_watcher
        self.stop_event = stop_event
        self.output_callback = output_callback

    def run(self):
        if not os.path.exists(self.log_path):
            msg = f"{APP_NAME}: File not found: {self.log_path}"
            logging.error(msg)
            if self.output_callback:
                self.output_callback(msg)
            return
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                f.seek(0, 2)
                while not self.stop_event.is_set():
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    self.process_line(line.strip())
        except Exception as e:
            logging.error(f"{APP_NAME}: Error monitoring {self.log_path}: {e}", exc_info=True)
            if self.output_callback:
                self.output_callback(f"Error monitorizando {self.log_path}: {e}")

    def process_line(self, line):
        if self.config_watcher.check_for_changes():
            # Opcional: Notificar cambio en config de mensajes
            pass

        cfg = self.config_watcher.config

        try:
            # Aqui puedes ampliar los patrones regex para mas eventos
            match_game = re.search(r"creating game \[(.*)\]", line)
            if match_game:
                game_name = match_game.group(1)
                template = cfg["MESSAGES"].get("messagecreate", "Game created: {game_name}")
                msg = template.replace("{game_name}", game_name)
                self.send_webhook(msg)
                if self.output_callback:
                    self.output_callback(f"[{self.log_path}] {msg}")
                return

            match_player = re.search(r"player \[(.*)\|(.+?)\] joined the game", line)
            if match_player:
                user = match_player.group(1)
                ip = match_player.group(2)
                template = cfg["MESSAGES"].get("messageplayer", "{user} connected from {ip}")
                msg = template.replace("{user}", user).replace("{ip}", ip)
                self.send_webhook(msg)
                if self.output_callback:
                    self.output_callback(f"[{self.log_path}] {msg}")
                return

            match_leave = re.search(r"deleting player \[(.*)\]:", line)
            if match_leave:
                user = match_leave.group(1)
                template = cfg["MESSAGES"].get("messagetoleave", "{user} left the game")
                msg = template.replace("{user}", user)
                self.send_webhook(msg)
                if self.output_callback:
                    self.output_callback(f"[{self.log_path}] {msg}")
                return

            match_connect = re.search(r"connecting to server \[(.*?)\]", line)
            if match_connect:
                server = match_connect.group(1)
                template = cfg["MESSAGES"].get("messagetoconnect", "Connected to server {SERVIDOR}")
                msg = template.replace("{SERVIDOR}", server)
                self.send_webhook(msg)
                if self.output_callback:
                    self.output_callback(f"[{self.log_path}] {msg}")
                return

            match_chat = re.search(r"\[Lobby\] (.+)", line)
            if match_chat:
                chat_msg = match_chat.group(0)
                self.send_webhook(chat_msg)
                if self.output_callback:
                    self.output_callback(f"[{self.log_path}] {chat_msg}")
                return
        except Exception as e:
            logging.error(f"Error procesando linea: {line} - {e}", exc_info=True)
            if self.output_callback:
                self.output_callback(f"Error procesando linea: {line} - {e}")

    def send_webhook(self, msg):
        try:
            res = requests.post(self.webhook, json={"content": msg})
            if res.status_code != 204:
                logging.error(f"{APP_NAME}: Webhook error {res.status_code}: {res.text}")
                if self.output_callback:
                    self.output_callback(f"Error webhook {res.status_code}: {res.text}")
        except Exception as e:
            logging.error(f"{APP_NAME}: Webhook send error: {e}", exc_info=True)
            if self.output_callback:
                self.output_callback(f"Error enviando webhook: {e}")

class GhostMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.dark_mode = tk.BooleanVar(value=False)
        self.minimize_tray = tk.BooleanVar(value=False)

        self.config_watcher = ConfigWatcher(CONFIG_INI_PATH)
        self.monitors = []
        self.monitor_stop_events = []

        self.data = []

        self.setup_ui()
        self.load_settings()
        self.apply_theme()

        self.tray_icon = None
        if pystray:
            self.setup_tray_icon()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        logging.info("Aplicacion iniciada correctamente")

    def setup_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab_logs = ttk.Frame(notebook)
        notebook.add(self.tab_logs, text="Monitoreo Logs")
        self.setup_logs_tab()

        self.tab_messages = ttk.Frame(notebook)
        notebook.add(self.tab_messages, text="Mensajes")
        self.setup_messages_tab()

        self.tab_config = ttk.Frame(notebook)
        notebook.add(self.tab_config, text="Configuracion")
        self.setup_config_tab()

        self.tab_output = ttk.Frame(notebook)
        notebook.add(self.tab_output, text="Logs en vivo")
        self.setup_output_tab()

    def setup_logs_tab(self):
        frame = self.tab_logs

        columns = ("logfile", "webhook")
        self.tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)
        self.tree.heading("logfile", text="Archivo LOG")
        self.tree.heading("webhook", text="Webhook URL")
        self.tree.column("logfile", width=350)
        self.tree.column("webhook", width=350)
        self.tree.grid(row=0, column=0, columnspan=4, pady=10, padx=10)

        ttk.Button(frame, text="Anadir", command=self.add_log).grid(row=1, column=0, padx=5, sticky='ew')
        ttk.Button(frame, text="Eliminar", command=self.delete_selected_log).grid(row=1, column=1, padx=5, sticky='ew')
        ttk.Button(frame, text="Cargar", command=self.load_data).grid(row=1, column=2, padx=5, sticky='ew')
        ttk.Button(frame, text="Guardar", command=self.save_data).grid(row=1, column=3, padx=5, sticky='ew')

        ttk.Button(frame, text="Iniciar Monitoreo", command=self.start_monitoring).grid(row=2, column=0, columnspan=4, sticky='ew', pady=10)

    def setup_messages_tab(self):
        frame = self.tab_messages
        self.msg_entries = {}
        row = 0
        for key in sorted(self.config_watcher.config["MESSAGES"].keys()):
            ttk.Label(frame, text=key).grid(row=row, column=0, sticky='w', padx=10, pady=5)
            entry = ttk.Entry(frame, width=60)
            entry.insert(0, self.config_watcher.config["MESSAGES"][key])
            entry.grid(row=row, column=1, sticky='ew', padx=10, pady=5)
            self.msg_entries[key] = entry
            row += 1

        ttk.Button(frame, text="Guardar mensajes", command=self.save_messages).grid(row=row, column=0, columnspan=2, pady=10)

    def setup_config_tab(self):
        frame = self.tab_config

        ttk.Checkbutton(frame, text="Modo oscuro", variable=self.dark_mode, command=self.toggle_dark_mode).grid(row=0, column=0, sticky='w', padx=10, pady=10)
        ttk.Checkbutton(frame, text="Minimizar a bandeja", variable=self.minimize_tray).grid(row=1, column=0, sticky='w', padx=10, pady=10)
        ttk.Button(frame, text="Salir", command=self.exit_app).grid(row=2, column=0, sticky='ew', padx=10, pady=20)

    def setup_output_tab(self):
        frame = self.tab_output
        self.txt_output = tk.Text(frame, state='disabled', bg='#1e1e1e', fg='white')
        self.txt_output.pack(fill='both', expand=True)

    def add_log(self):
        log_path = filedialog.askopenfilename(title="Selecciona archivo LOG")
        if log_path:
            webhook = simpledialog.askstring("Webhook", "Ingrese URL webhook Discord:")
            if webhook:
                self.tree.insert("", "end", values=(log_path, webhook))
                self.data.append({"logfile": log_path, "webhook": webhook})

    def delete_selected_log(self):
        selected = self.tree.selection()
        for sel in selected:
            vals = self.tree.item(sel)["values"]
            self.data = [d for d in self.data if d["logfile"] != vals[0]]
            self.tree.delete(sel)

    def save_data(self):
        self.data = []
        for child in self.tree.get_children():
            vals = self.tree.item(child)["values"]
            self.data.append({"logfile": vals[0], "webhook": vals[1]})
        try:
            os.makedirs(os.path.dirname(CONFIG_JSON_PATH), exist_ok=True)
            with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            self.log_output(f"Configuracion guardada en {CONFIG_JSON_PATH}")
            logging.info("Configuracion guardada correctamente")
        except Exception as e:
            self.log_output(f"Error guardando configuracion: {e}")
            logging.error(f"Error guardando configuracion: {e}", exc_info=True)

    def load_data(self):
        if os.path.exists(CONFIG_JSON_PATH):
            try:
                with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                self.tree.delete(*self.tree.get_children())
                for entry in self.data:
                    self.tree.insert("", "end", values=(entry["logfile"], entry["webhook"]))
                self.log_output(f"Configuracion cargada desde {CONFIG_JSON_PATH}")
                logging.info("Configuracion cargada correctamente")
            except Exception as e:
                self.log_output(f"Error cargando configuracion: {e}")
                logging.error(f"Error cargando configuracion: {e}", exc_info=True)

    def save_messages(self):
        for key, entry in self.msg_entries.items():
            self.config_watcher.config["MESSAGES"][key] = entry.get()
        try:
            os.makedirs(os.path.dirname(CONFIG_INI_PATH), exist_ok=True)
            with open(CONFIG_INI_PATH, "w", encoding="utf-8") as f:
                self.config_watcher.config.write(f)
            self.log_output("Mensajes guardados correctamente")
            logging.info("Mensajes guardados en config ini")
        except Exception as e:
            self.log_output(f"Error guardando mensajes: {e}")
            logging.error(f"Error guardando mensajes: {e}", exc_info=True)

    def toggle_dark_mode(self):
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode.get():
            bg = "#222222"
            fg = "white"
            self.root.configure(bg=bg)
            style = ttk.Style()
            style.theme_use("clam")
            style.configure(".", background=bg, foreground=fg, fieldbackground=bg)
            style.map("Treeview", background=[('selected', '#444444')], foreground=[('selected', 'white')])
            self.txt_output.configure(bg="#1e1e1e", fg="white")
        else:
            bg = "SystemButtonFace"
            fg = "black"
            self.root.configure(bg=bg)
            style = ttk.Style()
            style.theme_use("default")
            self.txt_output.configure(bg="white", fg="black")

    def start_monitoring(self):
        if self.monitor_stop_events:
            self.stop_monitoring()

        self.save_data()
        self.monitors.clear()
        self.monitor_stop_events.clear()

        for entry in self.data:
            stop_event = threading.Event()
            thread = MonitorThread(entry["logfile"], entry["webhook"], self.config_watcher, stop_event, self.log_output)
            thread.start()
            self.monitors.append(thread)
            self.monitor_stop_events.append(stop_event)
            self.log_output(f"Monitor iniciado: {entry['logfile']}")
            logging.info(f"Monitor iniciado para archivo: {entry['logfile']}")

        self.log_output("Todos los monitores iniciados")
        logging.info("Todos los monitores iniciados")

    def stop_monitoring(self):
        for event in self.monitor_stop_events:
            event.set()
        self.monitors.clear()
        self.monitor_stop_events.clear()
        self.log_output("Monitoreo detenido")
        logging.info("Monitoreo detenido")

    def log_output(self, msg):
        self.txt_output.configure(state='normal')
        self.txt_output.insert("end", msg + "\n")
        self.txt_output.see("end")
        self.txt_output.configure(state='disabled')
        logging.debug(msg)

    def exit_app(self):
        self.stop_monitoring()
        logging.info("Aplicacion cerrada por el usuario")
        self.root.destroy()

    def setup_tray_icon(self):
        if not pystray:
            return
        # Crear icono simple para bandeja
        image = Image.new('RGB', (64, 64), color='black')
        d = ImageDraw.Draw(image)
        d.rectangle([16, 16, 48, 48], fill="white")

        def on_quit(icon, item):
            self.exit_app()
            icon.stop()

        def on_show(icon, item):
            self.root.deiconify()

        menu = pystray.Menu(
            pystray.MenuItem('Mostrar', on_show),
            pystray.MenuItem('Salir', on_quit)
        )
        self.tray_icon = pystray.Icon(APP_NAME, image, menu=menu)

    def on_close(self):
        if self.minimize_tray.get() and pystray:
            self.root.withdraw()
            self.tray_icon.run_detached()
            self.log_output("Minimizado a bandeja")
            logging.info("Minimizado a bandeja")
        else:
            self.exit_app()

    def load_settings(self):
        self.load_data()
        self.dark_mode.set(False)
        self.minimize_tray.set(False)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = GhostMonitorApp(root)
        root.mainloop()
    except Exception:
        logging.error("Error critico en la aplicacion", exc_info=True)
