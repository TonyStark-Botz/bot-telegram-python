#!/bin/bash

# Script de inicialização para servidores Linux compartilhados (como Hostinger)

# Definir o caminho para o diretório do projeto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$PROJECT_DIR"

# Criar diretórios para logs se não existirem
mkdir -p logs

# Verificar se Python está instalado
if ! command -v python3 &>/dev/null; then
    echo "Python 3 não está instalado!"
    exit 1
fi

# Verificar se o arquivo .env existe
if [ ! -f .env ]; then
    echo "Arquivo .env não encontrado. Crie o arquivo com as credenciais necessárias."
    exit 1
fi

# Verificar e instalar dependências
if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
fi

# Ativar ambiente virtual
source venv/bin/activate

# Instalar ou atualizar dependências
echo "Instalando dependências..."
pip install -r requirements.txt

# Iniciar o bot e o monitor como processos em background
echo "Iniciando o bot..."
nohup python3 main.py >> logs/bot.log 2>&1 &
echo $! > bot.pid

echo "Iniciando o monitor..."
nohup python3 monitor.py >> logs/monitor.log 2>&1 &
echo $! > monitor.pid

echo "Bot e monitor iniciados com sucesso! Logs disponíveis em ./logs/"