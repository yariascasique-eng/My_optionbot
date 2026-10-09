import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from supabase import create_client, Client

# Configuración de logs para ver actividad en Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno desde Render
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Inicializar clientes
groq_client = Groq(api_key=GROQ_API_KEY)
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Función para el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "¡Hola! 👋 Bienvenido a **My_optionbot**.\n\n"
        "Soy tu asistente virtual de educación financiera y trading simulado. "
        "¿En qué puedo ayudarte hoy?"
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

# Función para procesar mensajes de texto
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "Usuario"

    logger.info(f"Mensaje recibido de {username} ({user_id}): {user_text}")

    try:
        # Llamada a Groq con el modelo activo y correcto
        response = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un asistente virtual experto en educación financiera y opciones binarias/financieras. "
                        "Responde de forma clara, profesional, concisa y educativa."
                    )
                },
                {"role": "user", "content": user_text}
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        reply_text = response.choices[0].message.content

        # Guardar historial en Supabase
        try:
            supabase_client.table("chat_history").insert({
                "user_id": user_id,
                "username": username,
                "user_message": user_text,
                "bot_response": reply_text
            }).execute()
        except Exception as db_err:
            logger.error(f"Error al guardar en Supabase: {db_err}")

        await update.message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Error con Groq: {e}")
        await update.message.reply_text("Ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo.")

# Punto de entrada principal
if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN no está configurado en las variables de entorno.")

    print("Bot ejecutándose...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Registradores de comandos y mensajes
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # Iniciar el bot en modo Polling
    app.run_polling()
