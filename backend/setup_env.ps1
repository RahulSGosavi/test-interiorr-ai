# PowerShell script to create .env file from template
# Run this script: .\setup_env.ps1

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "Environment Variables Setup" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env already exists
if (Test-Path ".env") {
    Write-Host "⚠️  .env file already exists!" -ForegroundColor Yellow
    $overwrite = Read-Host "Do you want to overwrite it? (y/N)"
    if ($overwrite -ne "y" -and $overwrite -ne "Y") {
        Write-Host "Cancelled. Existing .env file preserved." -ForegroundColor Yellow
        exit
    }
}

# Generate SECRET_KEY
Write-Host "Generating secure SECRET_KEY..." -ForegroundColor Green
$secretKey = python -c "import secrets; print(secrets.token_urlsafe(32))"

# Create .env file content
$envContent = @"
# ============================================
# Backend Environment Variables
# ============================================
# IMPORTANT: This file contains sensitive information!
# DO NOT commit this file to version control!

# ============================================
# Security & Authentication
# ============================================
# Secret key for JWT token signing
SECRET_KEY=$secretKey

# JWT token expiration time in minutes (43200 = 30 days)
ACCESS_TOKEN_EXPIRE_MINUTES=43200

# ============================================
# Database Configuration
# ============================================
# Primary database URL (leave empty to use SQLite)
# PostgreSQL example: postgresql://user:password@localhost:5432/dbname
DATABASE_URL=

# Fallback database URL (SQLite will be used if DATABASE_URL is empty)
FALLBACK_DATABASE_URL=

# ============================================
# File Upload Configuration
# ============================================
# Directory where uploaded files will be stored
UPLOAD_DIR=uploads

# ============================================
# AI Provider Configuration
# ============================================
# OpenAI API Key (get from https://platform.openai.com/api-keys)
OPENAI_API_KEY=

# OpenAI Model to use (default: gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini

# Google Gemini API Key (get from https://makersuite.google.com/app/apikey)
GEMINI_API_KEY=

# Gemini Model(s) to use (comma-separated for fallback)
GEMINI_MODEL=gemini-2.5-pro,gemini-2.0-pro-exp,gemini-2.0-pro-latest

# ============================================
# CORS Configuration
# ============================================
# Allowed CORS origins (comma-separated or * for all)
# Development: http://localhost:3000,http://localhost:3001
# Production: https://yourdomain.com
CORS_ORIGINS=*

# Allow credentials in CORS requests
CORS_ALLOW_CREDENTIALS=false
"@

# Write to .env file
$envContent | Out-File -FilePath ".env" -Encoding utf8 -NoNewline

Write-Host ""
Write-Host "✅ .env file created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Next steps:" -ForegroundColor Yellow
Write-Host "   1. Add your OPENAI_API_KEY (optional, for AI features)" -ForegroundColor White
Write-Host "   2. Add your GEMINI_API_KEY (optional, for AI features)" -ForegroundColor White
Write-Host "   3. Configure DATABASE_URL if using PostgreSQL/MySQL (optional)" -ForegroundColor White
Write-Host "   4. Update CORS_ORIGINS for production deployment" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  Remember: Never commit .env to version control!" -ForegroundColor Red
Write-Host ""

