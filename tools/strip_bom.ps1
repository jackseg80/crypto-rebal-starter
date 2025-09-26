Param(
    [string]$Root = "."
)
Write-Host "Stripping BOM (utf-8) sous $Root ..."
Get-ChildItem -Path $Root -Recurse -Include *.py, *.js, *.ts, *.json, *.html, *.css, *.md | ForEach-Object {
    $p = $_.FullName
    $bytes = [System.IO.File]::ReadAllBytes($p)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        [System.IO.File]::WriteAllBytes($p, $bytes[3..($bytes.Length - 1)])
        Write-Host "BOM supprimé -> $p"
    }
}
Write-Host "Terminé."