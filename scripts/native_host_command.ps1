# Development-only fixed load/unload commands for an existing owned local RCON.
# Never writes RCON settings, prints its password, or accepts arbitrary commands.
param(
    [Parameter(Mandatory=$true)][string]$Directory,
    [Parameter(Mandatory=$true)][ValidateSet('load','unload')][string]$Action
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
$planFile = Join-Path $Directory 'plan.json'
$plan = Get-Content -Raw -LiteralPath $planFile | ConvertFrom-Json
$config = Get-Content -LiteralPath (Join-Path $plan.bakkes 'cfg\config.cfg')
function Read-Setting([string]$Name) {
    $pattern = '^\s*' + [regex]::Escape($Name) + '\s+"([^"\r\n]*)"(?:\s*(?://.*)?)?$'
    $values = @($config | ForEach-Object { if ($_ -match $pattern) { $Matches[1] } })
    if ($values.Count -ne 1) { throw 'An unambiguous existing RCON setting was not found; use the in-game console.' }
    return $values[0]
}
$portText = Read-Setting 'rcon_port'
if ($portText -notmatch '^\d{4,5}$') { throw 'The configured RCON port is invalid.' }
$port = [int]$portText
$contextJson = & $pythonExe (Join-Path $PSScriptRoot 'native_host_trial.py') command-context $Directory --port $port
if ($LASTEXITCODE -ne 0) { throw 'The owned local game listener could not be verified.' }
$context = $contextJson | ConvertFrom-Json
if ($context.owned_listener -ne $true -or $context.plugin_name -notmatch '^MCTHostProbe_[a-f0-9]{32}$') {
    throw 'The diagnostic command context is invalid.'
}
$password = Read-Setting 'rcon_password'
if ($password.Length -lt 1 -or $password.Length -gt 128 -or $password -match '[\r\n;]') {
    throw 'The existing RCON password cannot be used by this diagnostic.'
}
$socket = [System.Net.WebSockets.ClientWebSocket]::new()
$deadline = [System.Threading.CancellationTokenSource]::new()
$deadline.CancelAfter(5000)
try {
    $null = $socket.ConnectAsync([uri]('ws://127.0.0.1:' + $port), $deadline.Token).GetAwaiter().GetResult()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes('rcon_password ' + $password)
    $null = $socket.SendAsync([System.ArraySegment[byte]]::new($bytes), [System.Net.WebSockets.WebSocketMessageType]::Text,
        $true, $deadline.Token).GetAwaiter().GetResult()
    [Array]::Clear($bytes, 0, $bytes.Length)
    $password = $null
    $response = [byte[]]::new(128)
    $received = $socket.ReceiveAsync([System.ArraySegment[byte]]::new($response), $deadline.Token).GetAwaiter().GetResult()
    if (-not $received.EndOfMessage -or $received.MessageType -ne [System.Net.WebSockets.WebSocketMessageType]::Text -or
        [System.Text.Encoding]::UTF8.GetString($response, 0, $received.Count) -ne 'authyes') {
        throw 'The existing local RCON did not authenticate the diagnostic.'
    }
    # Revalidate ownership immediately before sending the single fixed command.
    $null = & $pythonExe (Join-Path $PSScriptRoot 'native_host_trial.py') command-context $Directory --port $port
    if ($LASTEXITCODE -ne 0) { throw 'The diagnostic session changed before its command.' }
    $commandBytes = [System.Text.Encoding]::UTF8.GetBytes('plugin ' + $Action + ' ' + $context.plugin_name)
    $null = $socket.SendAsync([System.ArraySegment[byte]]::new($commandBytes), [System.Net.WebSockets.WebSocketMessageType]::Text,
        $true, $deadline.Token).GetAwaiter().GetResult()
    Write-Output ('Diagnostic ' + $Action + ' requested. Verify the plugin receipt before claiming success.')
} finally {
    $password = $null
    $socket.Dispose()
    $deadline.Dispose()
}
