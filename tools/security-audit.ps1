# Script de validation sécuritaire - Crypto Rebalancer
# Usage: .\tools\security-audit.ps1

Write-Host "🔒 Security Audit - Crypto Rebalancer" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green

$errors = 0
$warnings = 0

# 1. Vérifier qu'aucun secret n'est commité
Write-Host "`n1. Scanning for exposed secrets..." -ForegroundColor Yellow

if (Test-Path ".env") {
    Write-Host "❌ .env file found in repository root!" -ForegroundColor Red
    $errors++
} else {
    Write-Host "✅ No .env file in repository" -ForegroundColor Green
}

if (Test-Path ".env.example") {
    $envExample = Get-Content ".env.example" -Raw
    if ($envExample -match "[A-Za-z0-9]{20,}") {
        Write-Host "⚠️ .env.example might contain actual secrets" -ForegroundColor Yellow
        $warnings++
    } else {
        Write-Host "✅ .env.example appears clean" -ForegroundColor Green
    }
}

# 2. Vérifier les hooks pre-commit
Write-Host "`n2. Checking pre-commit configuration..." -ForegroundColor Yellow

if (Test-Path ".pre-commit-config.yaml") {
    $precommit = Get-Content ".pre-commit-config.yaml" -Raw
    if ($precommit -match "gitleaks" -and $precommit -match "detect-secrets") {
        Write-Host "✅ Pre-commit hooks configured with secret scanning" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Pre-commit hooks missing secret scanning" -ForegroundColor Yellow
        $warnings++
    }
} else {
    Write-Host "❌ No pre-commit configuration found" -ForegroundColor Red
    $errors++
}

# 3. Vérifier ESLint configuration
Write-Host "`n3. Checking ESLint security rules..." -ForegroundColor Yellow

if (Test-Path ".eslintrc.json") {
    $eslint = Get-Content ".eslintrc.json" -Raw | ConvertFrom-Json
    if ($eslint.rules."no-console" -and $eslint.rules."no-eval") {
        Write-Host "✅ ESLint configured with security rules" -ForegroundColor Green
    } else {
        Write-Host "⚠️ ESLint missing security rules" -ForegroundColor Yellow
        $warnings++
    }
} else {
    Write-Host "❌ No ESLint configuration found" -ForegroundColor Red
    $errors++
}

# 4. Scan pour console.log restants
Write-Host "`n4. Scanning for remaining console.log in frontend..." -ForegroundColor Yellow

$consoleLogCount = 0
if (Test-Path "static") {
    $jsFiles = Get-ChildItem "static" -Recurse -Filter "*.js" | Where-Object { $_.Name -notlike "*.min.js" }
    foreach ($file in $jsFiles) {
        $content = Get-Content $file.FullName -Raw
        $matches = [regex]::Matches($content, "console\.log\(")
        $consoleLogCount += $matches.Count
    }
}

if ($consoleLogCount -eq 0) {
    Write-Host "✅ No console.log found in frontend files" -ForegroundColor Green
} elseif ($consoleLogCount -lt 10) {
    Write-Host "⚠️ $consoleLogCount console.log found (acceptable for legacy files)" -ForegroundColor Yellow
    $warnings++
} else {
    Write-Host "❌ $consoleLogCount console.log found (too many)" -ForegroundColor Red
    $errors++
}

# 5. Vérifier debug-logger.js
Write-Host "`n5. Checking debug logger implementation..." -ForegroundColor Yellow

if (Test-Path "static/debug-logger.js") {
    $debugLogger = Get-Content "static/debug-logger.js" -Raw
    if ($debugLogger -match "debugEnabled" -and $debugLogger -match "localhost") {
        Write-Host "✅ Debug logger properly configured" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Debug logger may need review" -ForegroundColor Yellow
        $warnings++
    }
} else {
    Write-Host "❌ Debug logger not found" -ForegroundColor Red
    $errors++
}

# 6. Test des headers de sécurité (nécessite serveur running)
Write-Host "`n6. Testing security headers (requires running server)..." -ForegroundColor Yellow

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/" -Method HEAD -TimeoutSec 5 -ErrorAction Stop

    $securityHeaders = @("x-content-type-options", "x-frame-options", "content-security-policy")
    $missingHeaders = @()

    foreach ($header in $securityHeaders) {
        if (-not $response.Headers[$header]) {
            $missingHeaders += $header
        }
    }

    if ($missingHeaders.Count -eq 0) {
        Write-Host "✅ All critical security headers present" -ForegroundColor Green
    } else {
        Write-Host "❌ Missing security headers: $($missingHeaders -join ', ')" -ForegroundColor Red
        $errors++
    }
} catch {
    Write-Host "⚠️ Cannot test headers - server not running on localhost:8000" -ForegroundColor Yellow
    $warnings++
}

# 7. Vérifier les tests de sécurité
Write-Host "`n7. Checking security test coverage..." -ForegroundColor Yellow

if (Test-Path "tests/test_security_headers.py") {
    Write-Host "✅ Security headers test file exists" -ForegroundColor Green
} else {
    Write-Host "❌ No security test file found" -ForegroundColor Red
    $errors++
}

# 8. Quick scan for obvious secrets
Write-Host "`n8. Scanning for obvious secrets..." -ForegroundColor Yellow

try {
    $pyFiles = Get-ChildItem -Recurse -Filter "*.py" | Where-Object { $_.Name -notlike "*test*" -and $_.Name -notlike "*.example*" }
    $jsFiles = Get-ChildItem -Recurse -Filter "*.js" | Where-Object { $_.Name -notlike "*test*" -and $_.Name -notlike "debug-logger*" }

    $secretCount = 0
    foreach ($file in ($pyFiles + $jsFiles)) {
        $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
        if ($content) {
            if ($content -match 'api_key.*=.*[A-Za-z0-9]{15,}' -or $content -match 'secret.*=.*[A-Za-z0-9]{15,}') {
                Write-Host "⚠️ Potential secret pattern in $($file.Name)" -ForegroundColor Yellow
                $secretCount++
            }
        }
    }

    if ($secretCount -eq 0) {
        Write-Host "✅ No obvious secret patterns found" -ForegroundColor Green
    } else {
        Write-Host "⚠️ $secretCount files with potential secrets" -ForegroundColor Yellow
        $warnings++
    }
} catch {
    Write-Host "⚠️ Error scanning for secrets: $($_.Exception.Message)" -ForegroundColor Yellow
    $warnings++
}

# Résumé final
Write-Host "`n" + "="*50 -ForegroundColor Green
Write-Host "SECURITY AUDIT SUMMARY" -ForegroundColor Green
Write-Host "="*50 -ForegroundColor Green

if ($errors -eq 0 -and $warnings -eq 0) {
    Write-Host "🎉 Perfect security score! No issues found." -ForegroundColor Green
    exit 0
} elseif ($errors -eq 0) {
    Write-Host "✅ Good security posture. $warnings warning(s) to review." -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "❌ Security issues found: $errors error(s), $warnings warning(s)" -ForegroundColor Red
    Write-Host "Please address critical issues before deploying." -ForegroundColor Red
    exit 1
}