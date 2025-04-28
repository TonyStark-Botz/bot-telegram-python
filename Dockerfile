FROM python:3.10-slim

WORKDIR /app

# Copiar arquivos de dependências e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante dos arquivos
COPY . .

# Criar diretório para logs
RUN mkdir -p /app/logs

# Configurar timezone
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Dar permissão de execução aos scripts
RUN chmod +x /app/main.py /app/monitor.py

# Definir o entrypoint para o script de inicialização
CMD ["sh", "-c", "python monitor.py & python main.py"]