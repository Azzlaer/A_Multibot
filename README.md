# 🤖 A_Multibot

**Un sistema de control de archivos LOG para bots GhostOne y Ghost+ que permite enviar mensajes vía webhook desde distintos archivos LOG configurados individualmente.**

---

## 📑 Índice

1. 📖 [Descripción](#-descripción)  
2. ✨ [Características principales](#-características-principales)  
3. 🛠️ [Requisitos](#️-requisitos)  
4. 📥 [Instalación](#-instalación)  
5. ⚙️ [Configuración](#️-configuración)  
6. ▶️ [Ejecutar el bot](#️-ejecutar-el-bot)  
7. 📂 [Estructura del repositorio](#-estructura-del-repositorio)  
8. 🤝 [Contribuir](#-contribuir)  
9. 📜 [Licencia](#-licencia)  
10. 📬 [Contacto](#-contacto)  

## 📑 IMAGENES

![Descripci贸n de la imagen](https://github.com/Azzlaer/A_Multibot/blob/main/Capturas/Screenshot_1.png)
![Descripci贸n de la imagen](https://github.com/Azzlaer/A_Multibot/blob/main/Capturas/Screenshot_2.png)
![Descripci贸n de la imagen](https://github.com/Azzlaer/A_Multibot/blob/main/Capturas/Screenshot_3.png)
![Descripci贸n de la imagen](https://github.com/Azzlaer/A_Multibot/blob/main/Capturas/Screenshot_4.png)

## 📖 Descripción

**A_Multibot** es una herramienta escrita en Python (con soporte mínimo en Batch) diseñada para monitorear archivos de log generados por los bots GhostOne y Ghost+.  
Permite enviar estos logs a uno o más endpoints de webhook, configurando cuál archivo corresponde a cada webhook.

---

## ✨ Características principales

- 🔍 Observa múltiples archivos log específicos por bot.  
- 📤 Envía actualizaciones a endpoints webhook definidos.  
- 🧩 Flexible: puedes añadir más archivos o endpoints mediante configuración.  
- ⚡ Automatización sencilla mediante script batch de instalación.  

---

## 🛠️ Requisitos

- 🐍 Python 3.6+  
- 📦 Librerías especificadas en `requirements.txt`  

---

## 📥 Instalación

1. Clona este repositorio:  
   ```bash
   git clone https://github.com/Azzlaer/A_Multibot.git
   cd A_Multibot
   ```

2. Instala las dependencias necesarias:  
   ```bash
   pip install -r requirements.txt
   ```

3. Opcional: ejecuta el script `INSTALAR.bat` (sólo Windows) para configurar el entorno automáticamente.

---

## ⚙️ Configuración

1. Edita el archivo `logs_config.txt` para especificar:

   - 📄 Qué archivos `.log` monitorear.  
   - 🌐 A qué webhook endpoint enviar las novedades.  

2. Verifica la configuración y guarda los cambios.

---

## ▶️ Ejecutar el bot

Para iniciar el bot, tienes varias opciones según la versión que quieras usar:

```bash
python main.py
```

También puedes usar variantes más específicas:

- 🛠️ `main_fix.py`: versión con correcciones adicionales.  
- 🪶 `main_minimo.py`: versión reducida, ideal para configuraciones básicas o pruebas rápidas.  

---

## 📂 Estructura del repositorio

- `main.py` – 🚀 Programa principal.  
- `main_fix.py` – 🛠️ Variante corregida.  
- `main_minimo.py` – 🪶 Versión simplificada.  
- `logs_config.txt` – ⚙️ Configuración de archivos y webhooks.  
- `INSTALAR.bat` – 🖥️ Script de instalación automatizada (Windows).  
- `requirements.txt` – 📦 Dependencias en Python.  
- 📁 `data/` – Archivos de datos (logs, ejemplos de configuración, etc.).  
- 📁 `config/` – Configuración adicional (si corresponde).  
- 📦 Archivos como `Multi_Bot.rar` para ejemplos o respaldo.  

---

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! 🙌  
Abre un _issue_ o envía un _pull request_ para:

- 💡 Sugerir nuevas características.  
- 🐞 Reportar errores.  
- 📚 Mejorar documentación o configuración.  

Por favor, sigue el estilo de codificación existente y describe claramente los cambios propuestos.

---

## 📜 Licencia

⚠️ No se ha definido una licencia en el repositorio.  
Si deseas adoptar una (MIT, Apache 2.0, etc.), indícalo aquí para permitir un uso más claro.

---

## 📬 Contacto

📩 Para dudas o feedback, abre un _issue_ en el repositorio o contacta al autor del proyecto.

---
