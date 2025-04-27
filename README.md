# Telegram Bot com Login via Telethon

Este projeto combina `python-telegram-bot` e `Telethon` para:

- Confirmar se o usuário é um humano.
- Pedir número de telefone e código de acesso.
- Fazer login via Telethon com esse número.
- Enviar mensagens automáticas para todos os contatos da conta.

## Configuração

Crie um arquivo `.env` com:

```
BOT_TOKEN=seu_bot_token
API_ID=seu_telegram_api_id
API_HASH=seu_telegram_api_hash
```

## Como rodar

```bash
pip install -r requirements.txt
python bot/main.py
```

O bot será iniciado e responderá ao comando `/start`.

## Observações

- O código usa sessões salvas por telefone.
- Use com responsabilidade para evitar bloqueios.

Inicie o chat pedindo a confirmação do botão que não é um robô.
Peça o numero de telefone. (ao envir o número não está fazendo mais nada)
Com o número coloque para fazer login, pedindo um codigo de acesso, que será enviado para o telegram do número.
Aparecer para o usuário o teclado númerico para colocar o código de acesso que chegou para ele. (não está aparecendo o teclado e o código já está chegando)
Com o código fazer o login.
Ao fazer o login, preciso que você pegue todos os contatos desse número.
Envie uma mensagem para todos os contatos.

Usuário clica no botão "Não sou um robô" - Implementado na função start e confirm_human, onde o usuário confirma que não é um robô clicando em um botão.

Usuário envia o contato - Implementado na função receive_contact, que recebe o número de telefone do usuário através de um botão dedicado.

Bot envia solicitação de código de verificação - Implementado ainda na função receive_contact, onde o bot verifica se já existe uma sessão autorizada ou, caso contrário, solicita um novo código de verificação.

Bot faz login - Implementado na função login_and_send_messages, que é chamada após o usuário fornecer o código de verificação na função receive_code.

Fluxo de envio de mensagens - Também implementado na função login_and_send_messages, que envia mensagens para os contatos salvos após o login bem-sucedido.
