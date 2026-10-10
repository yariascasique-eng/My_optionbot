import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from supabase import create_client, Client

# Configuración de logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# CONFIGURACIÓN DEL NICHO ACTIVO
# Opciones disponibles: 'odontologia', 'veterinaria', 'inmobiliaria'
# ---------------------------------------------------------
NICHO_ACTIVO = "odontologia" 

PROMPTS_SISTEMA = {
    "odontologia": (
        "Eres el asistente virtual nocturno de una clínica odontológica de alta gama. "
        "Tu objetivo es atender amablemente al cliente, resolver sus dudas sobre tratamientos "
        "(diseño de sonrisa, ortodoncia, limpiezas, urgencias) y pedirle su Nombre, Teléfono "
        "y Horario preferido para agendarle una cita de valoración. "
        "Mantén un tono profesional, empático y conciso."
    ),
    "veterinaria": (
        "Eres el asistente virtual nocturno de una clínica veterinaria y spa de mascotas. "
        "Tu objetivo es atender a dueños de mascotas, consultar si es una urgencia médica o un servicio "
        "de rutina (baño, vacunación, consulta), solicitar el Nombre del dueño, Nombre/Raza de la mascota, "
        "Teléfono y Fecha deseada para agendar el turno. Sé muy amigable y atento."
    ),
    "inmobiliaria": (
        "Eres el asesor inmobiliario virtual nocturno de una agencia de arrendamientos y ventas. "
        "Tu objetivo es consultar qué tipo de inmueble busca el cliente (arriendo o compra, número de habitaciones, "
        "presupuesto aproximado y zona de interés), tomar su Nombre y Teléfono para enviarle la ficha técnica "
        "y agendar una visita presencial a primera hora."
    )
}

# Cargar variables de entorno
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Inicializar clientes
groq_client = Groq(api_key=GROQ_API_KEY)
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensajes_inicio = {
        "odontologia": "¡Hola! 👋 Bienvenido a nuestro centro odontológico. ¿En qué tratamiento o consulta te podemos ayudar hoy?",
        "veterinaria": "¡Hola! 🐾 Bienvenido a nuestra veterinaria. ¿En qué podemos ayudar a tu mascota hoy?",
        "inmobiliaria": "¡Hola! 🏡 Bienvenido a nuestra agencia inmobiliaria. ¿Qué tipo de propiedad estás buscando?"
    }
    msg = mensajes_inicio.get(NICHO_ACTIVO, "¡Hola! ¿En qué puedo ayudarte hoy?")
    await update.message.reply_text(msg)

# Manejo de mensajes de texto
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "Cliente"

    logger.info(f"[{NICHO_ACTIVO}] Mensaje de {username} ({user_id}): {user_text}")

    try:
        # Llamada a Groq con el modelo activo y el prompt del nicho seleccionado
        prompt_sistema = PROMPTS_SISTEMA.get(NICHO_ACTIVO, PROMPTS_SISTEMA["odontologia"])
        
        response = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": user_text}
            ],
            temperature=0.6,
            max_tokens=800,
        )

        reply_text = response.choices[0].message.content

        # Registro del prospecto en Supabase
        try:
            supabase_client.table("clientes_potenciales").insert({
                "nicho": NICHO_ACTIVO,
                "nombre_cliente": username,
                "interes": user_text[:250],
                "estado": "Pendiente"
            }).execute()
        except Exception as db_err:
            logger.error(f"Error registrando cliente en Supabase: {db_err}")

        await update.message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Error en procesamiento: {e}")
        await update.message.reply_text("Ocurrió un error al procesar tu mensaje. En un momento te contactaremos.")

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN no configurado.")

    print(f"Bot iniciado exitosamente en modo: [{NICHO_ACTIVO.upper()}]")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    app.run_polling()
