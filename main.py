import logging
import sys
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
MAIN_CONFIG_PATH = "config/config.ini"


# ==========================
#  CONFIGURACIÓN GLOBAL
# ==========================

class AppConfig:
    def __init__(self, ini_path=MAIN_CONFIG_PATH):
        self.ini_path = ini_path
        self.config = configparser.ConfigParser()
        self.load()

    def load(self):
        if not os.path.exists(self.ini_path):
            self.create_default()
        self.config.read(self.ini_path, encoding="utf-8")

    def create_default(self):
        os.makedirs(os.path.dirname(self.ini_path), exist_ok=True)
        self.config["APP"] = {
            "mode": "GUI",          # GUI | TERMINAL | SERVICE
            "log_level": "INFO",
            "auto_start": "false"   # true = auto comenzar monitoreo en GUI
        }
        self.config["PATHS"] = {
            "config_ini": CONFIG_INI_PATH,
            "settings_json": CONFIG_JSON_PATH
        }
        with open(self.ini_path, "w", encoding="utf-8") as f:
            self.config.write(f)

    def get(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback)


# ==========================
#  LOGGING GLOBAL
# ==========================

def setup_logging(level="INFO"):
    lvl = getattr(logging, level.upper(), logging.INFO)
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        filename="logs/app.log",
        filemode="a",
        format="%(asctime)s %(levelname)s %(message)s",
        level=lvl
    )
    logging.info(f"{APP_NAME} iniciado en nivel {level}")


# ==========================
#  MANEJO DE EXCEPCIONES
# ==========================

def log_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = log_exception


# ==========================
#  CLASE DE WATCHER
# ==========================

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
                logging.info("Default messages updated")
                return True
        return False


# ==========================
#  HILO DE MONITOREO
# ==========================

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
            msg = f"{APP_NAME}: archivo no encontrado: {self.log_path}"
            logging.error(msg)
            if self.output_callback:
                self.output_callback(msg)
            return

        # 🔔 Log a Discord cuando arranca este monitor
        startup_msg = f"{APP_NAME}: monitor iniciado para {self.log_path}"
        self.send_webhook(startup_msg)
        logging.info(startup_msg)
        if self.output_callback:
            self.output_callback(startup_msg)

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                f.seek(0, 2)  # Ir al final del archivo
                while not self.stop_event.is_set():
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    self.process_line(line.strip())
        except Exception as e:
            logging.error(f"{APP_NAME}: Error monitorizando {self.log_path}: {e}", exc_info=True)
            if self.output_callback:
                self.output_callback(f"Error monitorizando {self.log_path}: {e}")

    def send_webhook(self, msg):
        try:
            res = requests.post(self.webhook, json={"content": msg})
            if res.status_code not in (200, 204):
                logging.error(f"{APP_NAME}: Webhook error {res.status_code}: {res.text}")
        except Exception as e:
            logging.error(f"{APP_NAME}: Webhook send error: {e}", exc_info=True)

    # ===== Detección de eventos ===== #
    def process_line(self, line):
        if self.config_watcher.check_for_changes():
            pass

        cfg = self.config_watcher.config

        try:
            # Crear partida
            match_game = re.search(r"creating game \[(.*)\]", line)
            if match_game:
                game_name = match_game.group(1)
                template = cfg["MESSAGES"].get("messagecreate", "Game created: {game_name}")
                msg = template.replace("{game_name}", game_name)
                self.send_webhook(msg)
                if self.output_callback:
                    self.output_callback(f"[{self.log_path}] {msg}")
                return

            # Entrada jugador
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

            # Salida jugador
            match_leave = re.search(r"deleting player \[(.*)\]:", line)
            if match_leave:
                user = match_leave.group(1)
                template = cfg["MESSAGES"].get("messagetoleave", "{user} left the game")
                msg = template.replace("{user}", user)
                self.send_webhook(msg)
                if self.output_callback:
                    self.output_callback(f"[{self.log_path}] {msg}")
                return

            # 🔥 Mensajes de chat
            # Soporta:
            # [GAME: DotA v6.85n #1] [Lobby] [User]: msg
            # [GAME: Pulpin War Arena #4] (22:31) [All] [User]: msg
            match_chat = re.search(
                r"\[GAME:\s*(.*?)\](?:.*?\((\d{1,2}:\d{2})\))?.*?\[(Lobby|All|Team|Observer)\]\s*\[(.*?)\]:\s*(.+)",
                line
            )
            if match_chat:
                game = match_chat.group(1).strip()
                user = match_chat.group(4).strip()
                message = match_chat.group(5).strip()

                msg = f"[{game}] {user}: {message}"

                self.send_webhook(msg)
                if self.output_callback:
                    self.output_callback(f"[{self.log_path}] {msg}")
                return

        except Exception as e:
            logging.error(f"Error procesando linea: {line} - {e}", exc_info=True)


# ==========================
#  GUI PRINCIPAL
# ==========================

class GhostMonitorApp:
    def __init__(self, root, app_config=None):
        self.root = root
        self.root.title(APP_NAME)

        self.app_config = app_config
        self.config_watcher = ConfigWatcher(CONFIG_INI_PATH)
        self.monitors = []
        self.monitor_stop_events = []
        self.data = []

        self.setup_ui()
        self.load_settings()

        # 🔁 AutoStart monitoreo si está activado en config.ini
        auto_start_str = "false"
        if self.app_config:
            auto_start_str = self.app_config.get("APP", "auto_start", "false")
        if auto_start_str.lower() == "true":
            self.log_output("AutoStart activo: iniciando monitoreo automáticamente...")
            self.start_monitoring()

    # ---- GUI ---- #
    def setup_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab_logs = ttk.Frame(notebook)
        notebook.add(self.tab_logs, text="Monitoreo Logs")
        self.setup_logs_tab()

        self.tab_output = ttk.Frame(notebook)
        notebook.add(self.tab_output, text="Logs en vivo")
        self.setup_output_tab()

    def setup_logs_tab(self):
        frame = self.tab_logs
        columns = ("logfile", "webhook")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        self.tree.heading("logfile", text="Archivo LOG")
        self.tree.heading("webhook", text="Webhook URL")
        self.tree.column("logfile", width=350)
        self.tree.column("webhook", width=350)
        self.tree.grid(row=0, column=0, columnspan=4, padx=10, pady=10)

        ttk.Button(frame, text="Añadir", command=self.add_log).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(frame, text="Guardar", command=self.save_data).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Iniciar", command=self.start_monitoring).grid(row=1, column=2, padx=5, pady=5)
        ttk.Button(frame, text="Detener", command=self.stop_monitoring).grid(row=1, column=3, padx=5, pady=5)

    def setup_output_tab(self):
        frame = self.tab_output
        self.txt_output = tk.Text(frame, state="disabled", bg="#1e1e1e", fg="white")
        self.txt_output.pack(fill="both", expand=True)

    def add_log(self):
        log_path = filedialog.askopenfilename(title="Seleccionar archivo LOG")
        if log_path:
            webhook = simpledialog.askstring("Webhook", "Ingrese URL Webhook Discord:")
            if webhook:
                self.tree.insert("", "end", values=(log_path, webhook))
                self.data.append({"logfile": log_path, "webhook": webhook})

    def save_data(self):
        self.data = []
        for child in self.tree.get_children():
            vals = self.tree.item(child)["values"]
            self.data.append({"logfile": vals[0], "webhook": vals[1]})

        os.makedirs(os.path.dirname(CONFIG_JSON_PATH), exist_ok=True)
        with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

        self.log_output("Configuración guardada en settings.json")

    def start_monitoring(self):
        self.save_data()
        self.stop_monitoring()

        for entry in self.data:
            stop_event = threading.Event()
            thread = MonitorThread(
                entry["logfile"],
                entry["webhook"],
                self.config_watcher,
                stop_event,
                self.log_output
            )
            thread.start()
            self.monitors.append(thread)
            self.monitor_stop_events.append(stop_event)

            self.log_output(f"Monitor iniciado para {entry['logfile']}")

    def stop_monitoring(self):
        for event in self.monitor_stop_events:
            event.set()
        self.monitors.clear()
        self.monitor_stop_events.clear()
        self.log_output("Monitoreo detenido")

    def log_output(self, msg):
        self.txt_output.configure(state="normal")
        self.txt_output.insert("end", msg + "\n")
        self.txt_output.see("end")
        self.txt_output.configure(state="disabled")
        logging.info(msg)

    def load_settings(self):
        if os.path.exists(CONFIG_JSON_PATH):
            try:
                with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                self.tree.delete(*self.tree.get_children())
                for entry in self.data:
                    self.tree.insert("", "end", values=(entry["logfile"], entry["webhook"]))
                self.log_output("Configuración cargada desde settings.json")
            except Exception as e:
                self.log_output(f"Error cargando configuración: {e}")
                logging.error(f"Error cargando configuración: {e}", exc_info=True)


# ==========================
#  EJECUCIÓN POR MODO
# ==========================

def run_gui(config):
    root = tk.Tk()
    app = GhostMonitorApp(root, app_config=config)
    root.mainloop()


def run_terminal(config):
    print(f"🧠 Iniciando {APP_NAME} en modo TERMINAL")
    watcher = ConfigWatcher(CONFIG_INI_PATH)
    stop_event = threading.Event()

    if not os.path.exists(CONFIG_JSON_PATH):
        print("❌ No se encontró settings.json")
        return

    with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    threads = []
    for entry in data:
        log_path = entry.get("logfile")
        webhook = entry.get("webhook")
        if log_path and webhook:
            t = MonitorThread(log_path, webhook, watcher, stop_event)
            t.start()
            threads.append(t)
            print(f"🟢 Monitor iniciado: {log_path}")

    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🟥 Deteniendo monitores...")
        stop_event.set()
        for t in threads:
            t.join()
        print("✅ Monitoreo detenido correctamente.")


def run_service(config):
    watcher = ConfigWatcher(CONFIG_INI_PATH)
    stop_event = threading.Event()
    print(f"🧩 {APP_NAME} ejecutándose en modo SERVICE...")

    # Servicio simple: levanta monitores según settings.json y los mantiene vivos
    if not os.path.exists(CONFIG_JSON_PATH):
        print("❌ No se encontró settings.json, nada que monitorear.")
        return

    with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    threads = []
    for entry in data:
        log_path = entry.get("logfile")
        webhook = entry.get("webhook")
        if log_path and webhook:
            t = MonitorThread(log_path, webhook, watcher, stop_event)
            t.start()
            threads.append(t)
            print(f"🟢 Monitor (SERVICE) iniciado: {log_path}")

    try:
        while not stop_event.is_set():
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🟥 Deteniendo servicio...")
        stop_event.set()
        for t in threads:
            t.join()
        print("✅ Servicio detenido correctamente.")


# ==========================
#  PUNTO DE ENTRADA
# ==========================

if __name__ == "__main__":
    cfg = AppConfig()
    setup_logging(cfg.get("APP", "log_level", "INFO"))

    mode = cfg.get("APP", "mode", "GUI").upper()
    print(f"🚀 Iniciando {APP_NAME} en modo {mode}")

    if mode == "GUI":
        run_gui(cfg)
    elif mode == "TERMINAL":
        run_terminal(cfg)
    elif mode == "SERVICE":
        run_service(cfg)
    else:
        print("⚠️ Modo no reconocido en config.ini (usa GUI, TERMINAL o SERVICE)")
