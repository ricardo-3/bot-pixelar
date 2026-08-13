import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from google import genai
import telebot

# Servidor web dummy para que Render no tire error de puerto
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Pixelar bot is alive!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# Configuración de Tokens
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Instrucciones de rol para tu Asistente de Estudio de la TUDD
INSTRUCCIONES_SISTEMA = (
    "Eres Pixelar, un asistente de estudio experto en diseño gráfico digital e interfaces (TUDD). "
    "Ayudas al usuario a llevar el seguimiento de sus clases, entregas y cronograma, "
    "explicando conceptos de usabilidad, heurísticas de Nielsen, Gestalt y affordances de forma clara, "
    "creativa y completamente libre de estereotipos o machismo."
)

@bot.message_handler(func=lambda message: True)
def responder_usuario(message):
    texto_usuario = message.text
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',  # <--- Modelo oficial actualizado
            contents=f"{INSTRUCCIONES_SISTEMA}\n\nUsuario dice: {texto_usuario}"
        )
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Ups, Pixelar tuvo un cortocircuito: {str(e)}")

print("¡Pixelar está online y listo en Telegram!")
bot.infinity_polling()
