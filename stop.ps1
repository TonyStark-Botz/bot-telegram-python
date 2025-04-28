# Script para encerrar os processos do bot no Windows

# Encerra o bot se estiver rodando
if (Test-Path "bot.pid") {
  $botPid = Get-Content "bot.pid"
  Write-Host "Encerrando o bot..."
  try {
    $process = Get-Process -Id $botPid -ErrorAction SilentlyContinue
    if ($process) {
      Stop-Process -Id $botPid -Force
      Write-Host "Bot encerrado (PID: $botPid)"
    }
    else {
      Write-Host "Bot não está rodando (mas arquivo PID existe)"
    }
    Remove-Item "bot.pid"
  }
  catch {
    Write-Host "Erro ao encerrar o processo do bot: $_"
  }
}
else {
  Write-Host "Arquivo bot.pid não encontrado"
}

# Encerra o monitor se estiver rodando
if (Test-Path "monitor.pid") {
  $monitorPid = Get-Content "monitor.pid"
  Write-Host "Encerrando o monitor..."
  try {
    $process = Get-Process -Id $monitorPid -ErrorAction SilentlyContinue
    if ($process) {
      Stop-Process -Id $monitorPid -Force
      Write-Host "Monitor encerrado (PID: $monitorPid)"
    }
    else {
      Write-Host "Monitor não está rodando (mas arquivo PID existe)"
    }
    Remove-Item "monitor.pid"
  }
  catch {
    Write-Host "Erro ao encerrar o processo do monitor: $_"
  }
}
else {
  Write-Host "Arquivo monitor.pid não encontrado"
}

# Verifica se existem outros processos relacionados
$botProcesses = Get-Process | Where-Object { $_.Name -eq "python" -or $_.Name -eq "python3" } | Where-Object { $_.CommandLine -like "*main.py*" -or $_.CommandLine -like "*monitor.py*" }
if ($botProcesses) {
  Write-Host "Encontrados outros processos Python relacionados ao bot:"
  foreach ($process in $botProcesses) {
    Write-Host "PID: $($process.Id), Nome: $($process.Name), Comando: $($process.CommandLine)"
    try {
      Stop-Process -Id $process.Id -Force
      Write-Host "Processo encerrado (PID: $($process.Id))"
    }
    catch {
      Write-Host "Erro ao encerrar o processo: $_"
    }
  }
}

Write-Host "Processos encerrados com sucesso!"