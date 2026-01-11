# Check Claude MCP logs to see the actual error

Write-Host "Checking Claude MCP logs..." -ForegroundColor Yellow
Write-Host ""

$logLocations = @(
    "$env:APPDATA\Claude\logs",
    "$env:LOCALAPPDATA\Claude\logs",
    "$env:USERPROFILE\.claude\logs"
)

foreach ($logPath in $logLocations) {
    if (Test-Path $logPath) {
        Write-Host "Found logs in: $logPath" -ForegroundColor Green
        
        # Get most recent log file
        $logFiles = Get-ChildItem -Path $logPath -Filter "*.log" -ErrorAction SilentlyContinue | 
            Sort-Object LastWriteTime -Descending | 
            Select-Object -First 3
        
        foreach ($log in $logFiles) {
            Write-Host ""
            Write-Host "=== $($log.Name) ===" -ForegroundColor Cyan
            Write-Host "Modified: $($log.LastWriteTime)" -ForegroundColor Gray
            Write-Host ""
            
            # Show last 30 lines
            $content = Get-Content $log.FullName -Tail 30 -ErrorAction SilentlyContinue
            $content | Write-Host
        }
    }
}

Write-Host ""
Write-Host "Also checking for mcp-server specific logs..." -ForegroundColor Yellow
Get-ChildItem -Path "$env:APPDATA\Claude" -Recurse -Filter "*mcp*.log" -ErrorAction SilentlyContinue | 
    ForEach-Object {
        Write-Host ""
        Write-Host "Found: $($_.FullName)" -ForegroundColor Green
        Get-Content $_.FullName -Tail 20
    }
