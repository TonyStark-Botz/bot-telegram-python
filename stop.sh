#!/bin/bash

# Script para parar o bot e o monitor

# Definir o caminho para o diretório do projeto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$PROJECT_DIR"

# Parar o bot se estiver rodando
if [ -f bot.pid ]; then
    echo "Parando o bot..."
    BOT_PID=$(cat bot.pid)
    if ps -p $BOT_PID > /dev/null; then
        kill $BOT_PID
        echo "Bot parado (PID: $BOT_PID)"
    else
        echo "Bot não está rodando"
    fi
    rm bot.pid
else
    echo "Arquivo bot.pid não encontrado"
fi

# Parar o monitor se estiver rodando
if [ -f monitor.pid ]; then
    echo "Parando o monitor..."
    MONITOR_PID=$(cat monitor.pid)
    if ps -p $MONITOR_PID > /dev/null; then
        kill $MONITOR_PID
        echo "Monitor parado (PID: $MONITOR_PID)"
    else
        echo "Monitor não está rodando"
    fi
    rm monitor.pid
else
    echo "Arquivo monitor.pid não encontrado"
fi

echo "Processos parados com sucesso!"