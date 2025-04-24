from telethon import TelegramClient
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.functions.messages import SendMessageRequest

api_id = 25462725
api_hash = "66a174ab12f849b8c3a1fe18352d5010"

# api_id = 21832746
# api_hash = "6a6cc3f9ef2c38453bf90bb63ab92d38"

async def login_and_send_messages(phone, code):
    client = TelegramClient(f"session_+{phone}", api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        try:
            print("Enviando solicitação de código para o número:", f'+{phone}')
            sent = await client.send_code_request(f'+{phone}')
            print(sent)
            
            # Aguarda o usuário inserir o código recebido
            code = input("Digite o código recebido na tela: ")
            while not code.strip():
                code = input("O código não pode estar vazio. Digite novamente: ")
            await client.sign_in(phone=f'+{phone}', code=code)
        except Exception as e:
            return f"Erro ao logar: {e}"

    try:
        result = await client(GetContactsRequest(hash=0))
        contacts = result.users
        for user in contacts:
            try:
                await client(SendMessageRequest(
                    peer=user.id,
                    message="Olá! Esta é uma mensagem automática.",
                    random_id=client.rnd_id()
                ))
            except:
                continue
        return f"Mensagens enviadas para {len(contacts)} contatos."
    finally:
        await client.disconnect()
