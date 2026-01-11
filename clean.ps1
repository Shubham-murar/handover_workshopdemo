Write-Host "Creating clean config..." -ForegroundColor Green

$configPath = "$env:APPDATA\Claude\claude_desktop_config.json"
$serverPath = "C:\Users\acer\Desktop\handover demo\handover_workshopdemo\better_mcp_server.py"

# Delete old file
if (Test-Path $configPath) {
    Remove-Item $configPath -Force
    Write-Host "Deleted old config" -ForegroundColor Yellow
}

# Create config object
$config = @{
    mcpServers = @{
        "workshop-patterns2" = @{
            command = "python"
            args = @($serverPath)
            env = @{}
        }
    }
}

# Convert to JSON
$json = $config | ConvertTo-Json -Depth 10

# Write without BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines($configPath, $json, $utf8NoBom)

Write-Host "Created config file" -ForegroundColor Green

# Verify
try {
    $test = Get-Content $configPath -Raw | ConvertFrom-Json
    Write-Host "Config is valid JSON" -ForegroundColor Green
    Write-Host "Server command: $($test.mcpServers.'workshop-patterns2'.command)" -ForegroundColor Cyan
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "1. Close Claude Desktop completely" -ForegroundColor Yellow
Write-Host "2. Wait 5 seconds" -ForegroundColor Yellow
Write-Host "3. Open Claude Desktop" -ForegroundColor Yellow
Write-Host "4. Ask Claude to use workshop-patterns2 tool" -ForegroundColor Yellow
