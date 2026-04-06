param()

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $workspaceRoot 'backend'
$frontendRoot = Join-Path $workspaceRoot 'frontend'
$pythonPath = Join-Path $workspaceRoot '.venv\Scripts\python.exe'

function Test-PortOpen {
    param(
        [string]$HostName,
        [int]$Port
    )

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $asyncResult = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne(1000, $false)) {
            $client.Close()
            return $false
        }

        $client.EndConnect($asyncResult)
        $connected = $client.Connected
        $client.Close()
        return $connected
    }
    catch {
        return $false
    }
}

if (-not (Test-PortOpen -HostName '127.0.0.1' -Port 8000)) {
    Start-Process -FilePath $pythonPath -WorkingDirectory $backendRoot -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--reload')
}

while (-not (Test-PortOpen -HostName '127.0.0.1' -Port 8000)) {
    Start-Sleep -Milliseconds 500
}

if (-not (Test-PortOpen -HostName '127.0.0.1' -Port 3000)) {
    Start-Process -FilePath 'npm.cmd' -WorkingDirectory $frontendRoot -ArgumentList @('run', 'dev')
}

while (-not (Test-PortOpen -HostName '127.0.0.1' -Port 3000)) {
    Start-Sleep -Milliseconds 500
}