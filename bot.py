import os
import logging
from collections import defaultdict, deque
from datetime import datetime
from zoneinfo import ZoneInfo

import telebot
from flask import Flask, request, abort
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pixelar")

# ---------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODELO = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL")

MEMORIA_TURNOS = 10

client = genai.Client(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ---------------------------------------------------------------
# Base de conocimiento (se lee del archivo conocimiento.md)
# ---------------------------------------------------------------
try:
    with open("conocimiento.md", encoding="utf-8") as f:
        CONOCIMIENTO = f.read()
    log.info("Base de conocimiento cargada: %d caracteres", len(CONOCIMIENTO))
except FileNotFoundError:
    CONOCIMIENTO = "(sin material cargado)"
    log.warning("No encontre conocimiento.md")

ROL = (
    "Eres Pixelar, el asistente de estudio de Rick para la materia "
    "Diseno de Interface de la Tecnicatura Universitaria en Diseno Digital "
    "(TUDD, UTN).\n\n"
    "TENES ACCESO AL MATERIAL REAL DE LA MATERIA (mas abajo). Usalo siempre "
    "como fuente principal. Cuando respondas sobre fechas, entregas o "
    "contenidos de clase, cita exactamente lo que dice el material. Si te "
    "preguntan algo que NO esta en el material (por ejemplo temas de las "
    "Unidades 2, 3 o 4, que todavia no tienen apunte), decilo con claridad: "
    "'esto no esta en el material que tengo cargado' y recien ahi responde "
    "con tu conocimiento general, avisando que es complemento.\n\n"
    "Sos claro, creativo, cercano y hablas en espanol rioplatense (vos, "
    "tenes, queres). Nada de estereotipos ni machismo.\n\n"
    "FORMATO OBLIGATORIO - escribis para Telegram. Usa SOLO estas etiquetas: "
    "<b>negrita</b>, <i>italica</i>, <code>codigo</code>. NUNCA uses "
    "asteriscos, almohadillas ni tablas de markdown: se ven rotos en "
    "Telegram. Para listas usa saltos de linea con numeros o emojis. "
    "Se conciso, menos de 300 palabras salvo que te pidan profundidad."
)


def instrucciones():
    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
    fecha = hoy.strftime("%d/%m/%Y")
    return (
        f"{ROL}\n\n"
        f"FECHA DE HOY: {fecha}. Usala para calcular cuantos dias faltan "
        f"para cada entrega cuando te pregunten.\n\n"
        f"===== MATERIAL DE LA MATERIA =====\n{CONOCIMIENTO}"
    )


# ---------------------------------------------------------------
# Memoria por chat
# ---------------------------------------------------------------
historial = defaultdict(lambda: deque(maxlen=MEMORIA_TURNOS))


def construir_contents(chat_id, texto_usuario):
    contents = []
    for rol, texto in historial[chat_id]:
        contents.append(types.Content(role=rol, parts=[types.Part(text=texto)]))
    contents.append(
        types.Content(role="user", parts=[types.Part(text=texto_usuario)])
    )
    return contents


def responder_seguro(message, texto):
    try:
        bot.reply_to(message, texto)
    except telebot.apihelper.ApiTelegramException:
        log.warning("HTML invalido, reenviando en texto plano")
        bot.reply_to(message, texto, parse_mode=None)


# ---------------------------------------------------------------
# Mensajes de error amigables
# ---------------------------------------------------------------
SIN_CUPO = (
    "\U0001FAAB <b>Uf, me quede sin nafta.</b>\n\n"
    "Como soy gratis, loco, Google me pone un limite de mensajes. "
    "Ya lo toque.\n\n"
    "No pidas mas por un rato: si fue el limite por minuto, en un "
    "minuto vuelvo. Si fue el del dia, se renueva a la madrugada "
    "(medianoche hora del Pacifico, o sea como las 4 o 5 AM aca).\n\n"
    "Banca a que se renueven los tokens... o paga \U0001F60E"
)

MODELO_CAIDO = (
    "\U0001F6E0 <b>Google cambio el modelo que uso.</b>\n\n"
    "Le pasa seguido: dan de baja modelos viejos. Hay que actualizar "
    "la variable <code>GEMINI_MODEL</code> en Render."
)


def clasificar_error(e):
    texto = str(e).lower()
    if "429" in texto or "resource_exhausted" in texto or "quota" in texto:
        return SIN_CUPO
    if "404" in texto or "not found" in texto or "no longer available" in texto:
        return MODELO_CAIDO
    return f"\U0001F635 Se me cruzaron los cables:\n<code>{e}</code>"


# ---------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "\U0001F3A8 <b>Hola! Soy Pixelar</b>, tu asistente de Diseno de "
        "Interface.\n\n"
        "Tengo cargado el cronograma completo, las fechas de entrega y los "
        "resumenes de las clases 1 a 4.\n\n"
        "Proba con:\n"
        "\U0001F4C5 <i>Que tengo que entregar esta semana?</i>\n"
        "\U0001F4DA <i>Explicame la ley de proximidad</i>\n"
        "\U0001F3AF <i>Tomame examen de las heuristicas de Nielsen</i>\n\n"
        "Comandos: /entregas - /reset",
    )


@bot.message_handler(commands=["entregas"])
def entregas(message):
    procesar(
        message,
        "Listame TODAS las actividades regulatorias con sus fechas de cierre "
        "y cuantos dias faltan desde hoy. Despues las no regulatorias.",
    )


@bot.message_handler(commands=["reset", "reiniciar"])
def reset(message):
    historial.pop(message.chat.id, None)
    bot.reply_to(message, "\U0001F9F9 Listo, borre nuestra charla. Arrancamos de cero.")


def procesar(message, texto_usuario):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, "typing")

    try:
        response = client.models.generate_content(
            model=MODELO,
            contents=construir_contents(chat_id, texto_usuario),
            config=types.GenerateContentConfig(
                system_instruction=instrucciones(),
                max_output_tokens=2000,
            ),
        )
        salida = (response.text or "").strip()
        if not salida:
            salida = "Se me quedo la mente en blanco. Proba reformulando?"

        historial[chat_id].append(("user", texto_usuario))
        historial[chat_id].append(("model", salida))
        responder_seguro(message, salida)

    except Exception as e:
        log.exception("Fallo generando respuesta")
        responder_seguro(message, clasificar_error(e))


@bot.message_handler(func=lambda m: True, content_types=["text"])
def responder_usuario(message):
    procesar(message, message.text)


# ---------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------
@app.route("/", methods=["GET"])
def health():
    return "Pixelar bot is alive!", 200


@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def recibir_update():
    if request.headers.get("content-type") != "application/json":
        abort(403)
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "", 200


def configurar_webhook():
    if not BASE_URL:
        log.warning("Sin RENDER_EXTERNAL_URL: modo local, no registro webhook")
        return
    bot.remove_webhook()
    bot.set_webhook(url=f"{BASE_URL}/{TELEGRAM_TOKEN}", drop_pending_updates=True)
    log.info("Webhook registrado")


configurar_webhook()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
