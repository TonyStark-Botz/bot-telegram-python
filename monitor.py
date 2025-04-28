#!/usr/bin/env python3
import os
import time
import subprocess
import requests
import logging
import psutil
import pathlib
from dotenv import load_dotenv

# Configuração de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Carrega as variáveis do arquivo .env
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
API_ENDPOINT = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"

# Garantir que a pasta de sessões exista
SESSIONS_DIR = pathlib.Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

def check_bot_is_running():
    """Verifica se o processo do bot está rodando."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Verifica se o processo é python e se está executando main.py
            if proc.info['name'] == 'python' or proc.info['name'] == 'python3':
                cmdline = ' '.join(proc.info['cmdline'] if proc.info['cmdline'] else [])
                if 'main.py' in cmdline:
                    return True, proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False, None

def check_bot_is_responsive():
    """Verifica se o bot está respondendo à API do Telegram."""
    try:
        response = requests.get(API_ENDPOINT, timeout=10)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except Exception as e:
        logger.error(f"Erro ao verificar API do Telegram: {e}")
        return False, None

def restart_bot():
    """Reinicia o processo do bot."""
    try:
        # Verifica se o bot está rodando
        running, pid = check_bot_is_running()
        
        # Se estiver rodando, mata o processo
        if running and pid:
            try:
                process = psutil.Process(pid)
                process.terminate()
                process.wait(timeout=5)  # Espera até 5 segundos para o processo terminar
            except psutil.TimeoutExpired:
                process.kill()  # Força o encerramento se demorar muito
            except Exception as e:
                logger.error(f"Erro ao terminar processo existente: {e}")
        
        # Aguarda um momento após matar o processo
        time.sleep(2)
        
        # Encontra o caminho absoluto do diretório atual
        dir_path = os.path.dirname(os.path.realpath(__file__))
        
        # Inicia o bot como um novo processo
        process = subprocess.Popen(
            ["python", os.path.join(dir_path, "main.py")],
            stdout=open(os.path.join(dir_path, "bot_output.log"), "a"),
            stderr=open(os.path.join(dir_path, "bot_errors.log"), "a")
        )
        
        logger.info(f"Bot reiniciado com sucesso, PID: {process.pid}")
        return True
    except Exception as e:
        logger.error(f"Erro ao reiniciar o bot: {e}")
        return False

def send_notification(message):
    """Envia uma notificação para um grupo ou contato específico."""
    try:
        # ID do chat para notificações (pode ser modificado para seu próprio chat)
        chat_id = os.getenv('NOTIFICATION_CHAT_ID', '-1002310545045') # Usar o ID do grupo de teste como padrão
        
        notification_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': f"📢 MONITOR BOT: {message}",
            'parse_mode': 'HTML'
        }
        
        response = requests.post(notification_url, data=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"Notificação enviada com sucesso: {message}")
            return True
        else:
            logger.error(f"Falha ao enviar notificação. Código: {response.status_code}, Resposta: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Erro ao enviar notificação: {e}")
        return False

def main():
    """Função principal do monitor."""
    logger.info("Monitor iniciado")
    send_notification("🟢 Monitor iniciado e verificando o bot Telegram")
    
    consecutive_failures = 0
    max_consecutive_failures = 3
    check_interval = 300  # 5 minutos
    
    while True:
        # Verifica se o bot está rodando
        is_running, pid = check_bot_is_running()
        
        # Se estiver rodando, verifica se está respondendo
        is_responsive = False
        if is_running:
            is_responsive, response_data = check_bot_is_responsive()
            logger.info(f"Status do bot: rodando={is_running} (PID={pid}), respondendo={is_responsive}")
        else:
            logger.warning("Bot não está rodando!")
        
        # Se não estiver rodando ou não estiver respondendo
        if not is_running or not is_responsive:
            consecutive_failures += 1
            logger.warning(f"Falha detectada! Contador: {consecutive_failures}/{max_consecutive_failures}")
            
            # Se atingiu o número máximo de falhas consecutivas
            if consecutive_failures >= max_consecutive_failures:
                msg = f"⚠️ Detectadas {consecutive_failures} falhas consecutivas. Reiniciando o bot..."
                logger.warning(msg)
                send_notification(msg)
                
                # Reinicia o bot
                if restart_bot():
                    consecutive_failures = 0  # Reseta o contador
                    send_notification("🟢 Bot reiniciado com sucesso!")
                else:
                    send_notification("🔴 Falha ao reiniciar o bot!")
        else:
            # Se está tudo funcionando, reseta o contador
            if consecutive_failures > 0:
                consecutive_failures = 0
                logger.info("Bot funcionando normalmente. Contador de falhas resetado.")
        
        # Aguarda o intervalo definido antes da próxima verificação
        logger.info(f"Próxima verificação em {check_interval} segundos")
        time.sleep(check_interval)

if __name__ == "__main__":
    main()