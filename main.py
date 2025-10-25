import logging
import sys
import time
import re
import os
import json
import configparser
import threading
import requests

# --- GUI imports (solo se usan si no está en modo nogui) ---
import argparse

APP_NAME = "GhostMonitorLOG"
CONFIG_INI_PATH = "config/default_messages.ini"
CONFIG_JSON_PATH = "data/settings.json"

logging.basicConfig(
    filename="app.log",
    filemode="a",
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)

def log(msg):
    print(msg)
    logging.info(msg)

# ---------------------------------------------------------------------
# CLASES COMPARTIDAS ENTRE GUI Y CLI
# ---------------------------------------------------------------------
class ConfigWatcher:
    def __init__(self, filepath):
        self.filepath = filepath
        self.last_mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else 0
        self.config = self.load_config()
        log(f"[ConfigWatcher] Usando archivo: {filepath}")

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
                log("[ConfigWatcher] Config actualizada")
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
            self._out(f"[{APP_NAME}] Archivo no encontrado: {self.log_path}")
            return

        self._out(f"[{APP_NAME}] Monitoreando: {self.log_path}")
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
            self._out(f"Error monitorizando {self.log_path}: {e}")

    def _out(self, msg):
        if self.output_callback:
            self.output_callback(msg)
        else:
            log(msg)

    def process_line(self, line):
        if self.config_watcher.check_for_changes():
            self._out("[Monitor] Config actualizada detectada")

        cfg = self.config_watcher.config
        try:
            match_game = re.search(r"creating game \[(.*)\]", line)
            if match_game:
                msg = cfg["MESSAGES"].get("messagecreate", "Game created: {game_name}").replace("{game_name}", match_game.group(1))
                return self.send_webhook(msg)

            match_player = re.search(r"player \[(.*)\|(.+?)\] joined the game", line)
            if match_player:
                msg = cfg["MESSAGES"].get("messageplayer", "{user} connected from {ip}") \
                    .replace("{user}", match_player.group(1)).replace("{ip}", match_player.group(2))
                return self.send_webhook(msg)

            match_leave = re.search(r"deleting player \[(.*)\]:", line)
            if match_leave:
                msg = cfg["MESSAGES"].get("messagetoleave", "{user} left the game").replace("{user}", match_leave.group(1))
                return self.send_webhook(msg)

            match_connect = re.search(r"connecting to server \[(.*?)\]", line)
            if match_connect:
                msg = cfg["MESSAGES"].get("messagetoconnect", "Connected to server {SERVIDOR}").replace("{SERVIDOR}", match_connect.group(1))
                return self.send_webhook(msg)

            match_chat = re.search(r"\[Lobby\] (.+)", line)
            if match_chat:
                return self.send_webhook(match_chat.group(0))

        except Exception as e:
            self._out(f"Error procesando línea: {e}")

    def send_webhook(self, msg):
        try:
            res = requests.post(self.webhook, json={"content": msg})
            if res.status_code == 204:
                self._out(f"[Webhook OK] {msg}")
            else:
                self._out(f"[Webhook Error {res.status_code}] {res.text}")
        except Exception as e:
            self._out(f"[Webhook Error] {e}")

# ---------------------------------------------------------------------
# MODO TERMINAL (NO GUI)
# ---------------------------------------------------------------------
def run_cli_mode():
    log(f"{APP_NAME} iniciado en modo consola (--nogui).")
    config_watcher = ConfigWatcher(CONFIG_INI_PATH)

    if not os.path.exists(CONFIG_JSON_PATH):
        log(f"No existe el archivo de configuración JSON: {CONFIG_JSON_PATH}")
        return

    try:
        with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log(f"Error leyendo {CONFIG_JSON_PATH}: {e}")
        return

    if not data:
        log("No hay archivos log configurados en settings.json.")
        return

    stop_events = []
    threads = []
    for entry in data:
        stop_event = threading.Event()
        thread = MonitorThread(entry["logfile"], entry["webhook"], config_watcher, stop_event)
        thread.start()
        stop_events.append(stop_event)
        threads.append(thread)
        log(f"Monitor iniciado para: {entry['logfile']}")

    log("Monitoreo activo. Presiona Ctrl+C para salir.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Cerrando monitores...")
        for event in stop_events:
            event.set()
        log("Programa finalizado.")

# ---------------------------------------------------------------------
# MODO GUI ORIGINAL (SOLO SI NO SE PASA --nogui)
# ---------------------------------------------------------------------
def run_gui_mode():
    import tkinter as tk
    from tkinter import ttk, filedialog, simpledialog, messagebox
    from PIL import Image, ImageDraw
    import pystray
    # Reimportamos la clase GhostMonitorApp del código original
    from main_gui import GhostMonitorApp  # archivo auxiliar para mantener limpio el código
    root = tk.Tk()
    app = GhostMonitorApp(root)
    root.mainloop()

# ---------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GhostMonitorLOG - multibot monitor")
    parser.add_argument("--nogui", action="store_true", help="Ejecutar en modo consola sin interfaz gráfica")
    args = parser.parse_args()

    if args.nogui:
        run_cli_mode()
    else:
        try:
            run_gui_mode()
        except Exception as e:
            log(f"Error iniciando GUI: {e}")
            log("Ejecutando en modo consola como respaldo...")
            run_cli_mode()
