import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from supabase import create_client, Client

# Servidor HTTP ligero para el Health Check de Render (Plan Gratuito)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Online")

def run_health_check():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Configuración de registros
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Variables de Entorno de la Nube
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Conexión a la IA y Base de Datos
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if (SUPABASE_URL and SUPABASE_KEY) else None

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id
    username = user.username or user.first_name
    
    if supabase:
        try:
            res = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
            if not res.data:
                supabase.table("users").insert({
                    "telegram_id": telegram_id,
                    "username": username,
                    "virtual_balance": 10000.00
                }).execute()
        except Exception as e:
            logging.error(f"Error en base de datos: {e}")

    await update.message.reply_text(
        f"¡Hola, {username}! 👋 Bienvenido a MyOptionBot.\n\n"
        "📈 Soy tu asistente de educación financiera e inteligencia artificial.\n\n"
        "Puedes hacerme cualquier pregunta sobre finanzas, trading, opciones financieras o conceptos de inversión.\n\n"
        "Comandos disponibles:\n"
        "• /saldo - Consulta tu saldo virtual de simulación ($10,000 USD)."
    )

# Comando /saldo
async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not supabase:
        await update.message.reply_text("Base de datos no conectada.")
        return
    
    try:
        res = supabase.table("users").select("virtual_balance").eq("telegram_id", telegram_id).execute()
        if res.data:
            balance = res.data[0]["virtual_balance"]
            await update.message.reply_text(f"💰 Tu saldo virtual de simulación es: ${balance:,.2f} USD")
        else:
            await update.message.reply_text("Por favor escribe /start primero para registrarte.")
    except Exception as e:
        await update.message.reply_text("Error al consultar el saldo.")
        logging.error(e)

# Manejador de respuestas de Inteligencia Artificial (Groq)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not groq_client:
        await update.message.reply_text("La IA no está configurada.")
        return
    
    await update.message.reply_chat_action("typing")
    
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "Eres MyOptionBot, un educador e instructor de finanzas, trading y opciones financieras. Tu tono es didáctico, empático, claro y profesional. Explica conceptos complejos de forma simple."
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ],
            temperature=0.7,
            max_tokens=1000
        )
        response = completion.choices[0].message.content
        await update.message.reply_text(response)
    except Exception as e:
        logging.error(f"Error con Groq: {e}")
        await update.message.reply_text("Ocurrió un error al procesar tu consulta con la IA. Intenta de nuevo.")

if __name__ == '__main__':
    # Iniciar servidor HTTP en segundo plano para mantener la aplicación viva en Render
    threading.Thread(target=run_health_check, daemon=True).start()
    
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: Falta TELEGRAM_BOT_TOKEN")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("saldo", saldo))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("Bot ejecutándose...")
        app.run_polling()
