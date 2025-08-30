import logging
import sys
import tkinter as tk

# Configurar logging
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
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = log_exception

def main():
    logging.info("Aplicación iniciada")
    root = tk.Tk()
    root.title("Test GhostMonitorLOG")
    label = tk.Label(root, text="Si ves esto, el GUI funciona")
    label.pack(padx=20, pady=20)
    root.mainloop()
    logging.info("Aplicación cerrada correctamente")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.error("Error crítico en main()", exc_info=True)
