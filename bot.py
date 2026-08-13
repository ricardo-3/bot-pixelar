import os
import telebot
from google import genai

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

INSTRUCCIONES_SISTEMA = "Eres Pixelar, un bot de diseño gráfico e interfaz creativo, experto y completamente libre de estereotipos o machismo. Ayudas a los usuarios con paletas de colores, tipografías, maquetación y buenas prácticas de diseño con un trato amable, profesional e inclusivo."

@bot.message_handler(func=lambda message: True)
def responder_usuario(message):
    texto_usuario = message.text
    try:
        respuesta = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{INSTRUCCIONES_SISTEMA}\n\nUsuario dice: {texto_usuario}"
        )
        bot.reply_to(message, respuesta.text)
    except Exception as e:
        bot.reply_to(message, "Ups, Pixelar tuvo un pequeño cortocircuito creativo. Inténtalo de nuevo.")

print("¡Pixelar está online y listo en Telegram!")
bot.infinity_polling()
