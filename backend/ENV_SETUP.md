# Environment Variables Setup Guide

This guide will help you set up your `.env` file with all the necessary secret keys and configuration.

## Quick Setup

1. **Copy the example file:**
   ```bash
   cd backend
   copy .env.example .env
   ```
   Or on Linux/Mac:
   ```bash
   cp .env.example .env
   ```

2. **Generate a secure SECRET_KEY:**
   ```bash
   python generate_secret_key.py
   ```
   Copy the generated key and add it to your `.env` file.

3. **Fill in your API keys:**
   - Get OpenAI API key from: https://platform.openai.com/api-keys
   - Get Gemini API key from: https://makersuite.google.com/app/apikey

## Environment Variables Explained

### Security & Authentication

- **SECRET_KEY**: Used for signing JWT tokens. **MUST be a strong random string.**
  - Generate one: `python generate_secret_key.py`
  - Or: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

- **ACCESS_TOKEN_EXPIRE_MINUTES**: How long JWT tokens remain valid (default: 43200 = 30 days)

### Database Configuration

- **DATABASE_URL**: Primary database connection string
  - PostgreSQL: `postgresql://user:password@localhost:5432/dbname`
  - MySQL: `mysql://user:password@localhost:3306/dbname`
  - Leave empty to use SQLite (default)

- **FALLBACK_DATABASE_URL**: Fallback database (usually not needed)

### File Upload

- **UPLOAD_DIR**: Directory for uploaded files (default: `uploads`)

### AI Provider Configuration

- **OPENAI_API_KEY**: Your OpenAI API key
- **OPENAI_MODEL**: Model to use (default: `gpt-4o-mini`)
- **GEMINI_API_KEY**: Your Google Gemini API key
- **GEMINI_MODEL**: Comma-separated list of Gemini models to try (with fallback)

### CORS Configuration

- **CORS_ORIGINS**: Allowed origins (comma-separated)
  - Development: `http://localhost:3000,http://localhost:3001`
  - Production: `https://yourdomain.com`
  - All origins: `*` (not recommended for production)

- **CORS_ALLOW_CREDENTIALS**: Allow credentials in CORS (true/false)

## Example .env File

```env
# Security
SECRET_KEY=your-generated-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=43200

# Database (leave empty for SQLite)
DATABASE_URL=
FALLBACK_DATABASE_URL=

# File Upload
UPLOAD_DIR=uploads

# AI Providers
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4o-mini
GEMINI_API_KEY=your-gemini-key-here
GEMINI_MODEL=gemini-2.5-pro,gemini-2.0-pro-exp

# CORS
CORS_ORIGINS=*
CORS_ALLOW_CREDENTIALS=false
```

## Security Notes

⚠️ **IMPORTANT:**
- Never commit `.env` to version control
- Use strong, unique SECRET_KEY in production
- Keep API keys secure and rotate them regularly
- Use environment-specific values for development vs production

## Verification

After creating your `.env` file, restart your backend server. The server will:
- Load all environment variables
- Use SQLite if DATABASE_URL is not set
- Log warnings if SECRET_KEY is using the default value

