import os
from dotenv import load_dotenv
import telebot
from agent import root_agent  # importa el agente desde agent.py

# ==============================
# 1️⃣ Cargar variables del entorno
# ==============================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("❌ No se encontró TELEGRAM_TOKEN en el archivo .env")

# ==============================
# 2️⃣ Crear bot de Telegram
# ==============================
bot = telebot.TeleBot(TOKEN)

# ==============================
# 3️⃣ Manejar mensajes entrantes
# ==============================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_text = message.text.strip()
    print(f"📩 Mensaje recibido: {user_text}")

    try:
        # Depuración: mostrar tipo y métodos del agente para entender cómo invocarlo
        print("DEBUG: root_agent tipo:", type(root_agent))
        try:
            attrs = [a for a in dir(root_agent) if not a.startswith("_")]
            callables = [a for a in attrs if callable(getattr(root_agent, a))]
            print("DEBUG: atributos públicos:", attrs)
            print("DEBUG: métodos públicos callable:", callables)
        except Exception as _:
            print("DEBUG: no se pudieron listar atributos del agente")

        # Try several common agent call patterns (robust against ADK/api changes)
        def call_agent(agent, text):
            # 1) try agent.run
            run_fn = getattr(agent, "run", None)
            if callable(run_fn):
                try:
                    return run_fn(text)
                except TypeError:
                    return run_fn([text])

            # 2) try generate
            gen_fn = getattr(agent, "generate", None)
            if callable(gen_fn):
                try:
                    return gen_fn(text)
                except TypeError:
                    return gen_fn([text])

            # 3) try invoke
            inv_fn = getattr(agent, "invoke", None)
            if callable(inv_fn):
                try:
                    return inv_fn(text)
                except TypeError:
                    return inv_fn([text])

            # 4) fallback: call the agent object itself
            if callable(agent):
                try:
                    return agent(text)
                except TypeError:
                    return agent([text])

            raise AttributeError("No supported call method found on agent")

        response = call_agent(root_agent, user_text)
        print("DEBUG: raw response:", repr(response))

        # Manejar distintos tipos de respuesta
        if hasattr(response, "text"):
            reply = response.text
        elif isinstance(response, list) and len(response) > 0 and hasattr(response[0], "text"):
            reply = response[0].text
        elif isinstance(response, dict) and "text" in response:
            reply = response["text"]
        else:
            reply = str(response)

        # Evitar enviar mensaje vacío a Telegram
        if not reply or str(reply).strip() == "":
            reply = "⚠️ El agente devolvió una respuesta vacía. Revisa la configuración/modelo y los logs."

        # Enviar respuesta al usuario
        bot.reply_to(message, reply)
        print(f"🤖 Respuesta enviada: {reply}")

    except Exception as e:
        error_msg = f"⚠️ Error procesando mensaje: {e}"
        bot.reply_to(message, error_msg)
        print(f"❌ {error_msg}")

# ==============================
# 4️⃣ Iniciar el bot
# ==============================
print("✅ Bot de Telegram conectado y esperando mensajes...")
bot.polling(non_stop=True)
