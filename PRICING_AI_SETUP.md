# Pricing AI Setup Guide

This guide explains how to enable and configure the Pricing AI feature in your application.

## Overview

The Pricing AI feature uses LiteLLM to connect to various AI providers (Gemini, OpenAI) to analyze documents, extract pricing information, perform calculations, and answer questions about your uploaded files.

## Prerequisites

The following packages are already included in `backend/requirements.txt`:
- `litellm` - Universal LLM integration library
- `openai` - OpenAI API client
- `pandas` - Data analysis for spreadsheets
- `PyMuPDF` - PDF text extraction
- `openpyxl` - Excel file support

## Configuration

### 1. Get API Keys

#### Option A: Google Gemini (Recommended - Free Tier Available)

1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Get API Key" or "Create API Key"
4. Copy your API key

#### Option B: OpenAI

1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy your API key

### 2. Set Environment Variables

Add the API keys to your deployment platform's environment variables:

#### For Render.com:
1. Go to your service dashboard
2. Navigate to "Environment" tab
3. Add these environment variables:

```
GEMINI_API_KEY=your-gemini-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
```

#### For Railway:
1. Go to your service settings
2. Navigate to "Variables" tab
3. Add the same environment variables as above

#### For Local Development:
Create a `.env` file in the `backend/` directory:

```bash
# backend/.env
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///./sql_app.db
UPLOAD_DIR=uploads

# AI Provider Keys
GEMINI_API_KEY=your-gemini-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
```

### 3. Restart Your Backend Service

After adding the environment variables:
- **Render/Railway**: The service will automatically redeploy
- **Local**: Restart the uvicorn server

```bash
cd backend
python -m uvicorn server:app --reload
```

## Features

Once configured, the Pricing AI can:

1. **Extract Information**: "What is the total cost of all items?"
2. **Find Data**: "List all unique cabinet codes"
3. **Calculate**: "What is the highest priced item?"
4. **Filter**: "Show me items with cost over $10,000"
5. **Summarize**: "Summarize the pricing by category"
6. **Analyze**: General questions about your documents

## Supported File Types

- **PDF**: Text extraction from CAD drawings, proposals, quotes
- **Excel (.xlsx, .xls)**: Spreadsheets with pricing data
- **CSV**: Comma-separated value files
- **Text (.txt)**: Plain text documents

## Provider Selection

In the Pricing AI page, you can choose between:
- **Gemini 2.0**: Google's latest model (fast, free tier)
- **GPT-4o**: OpenAI's model (powerful, requires credits)

## Troubleshooting

### Error: "AI integration is not available"
- The `litellm` package is not installed
- Run: `pip install -r backend/requirements.txt`

### Error: "AI provider authentication error"
- API key is missing or invalid
- Check that environment variables are set correctly
- Verify the API key is active in the provider's dashboard

### Error: "File type not supported"
- The uploaded file type cannot be analyzed
- Supported types: PDF, Excel, CSV, TXT

### Error: "Rate limit exceeded"
- You've exceeded the API provider's rate limits
- Wait a few minutes or upgrade your API plan
- Try switching to a different provider

## Cost Considerations

### Gemini API:
- Free tier: 60 queries per minute
- Paid tier: $0.00015 per 1K tokens (very affordable)

### OpenAI API:
- GPT-4o-mini: $0.15 per 1M input tokens, $0.60 per 1M output tokens
- Typical query cost: ~$0.01-0.05

## Security Notes

1. **Never commit API keys** to your git repository
2. Use environment variables for all sensitive data
3. Rotate API keys regularly
4. Monitor API usage in provider dashboards
5. Set spending limits if available

## Example Usage

After setup, try these example questions:

**For Pricing Documents:**
- "What is the total cost?"
- "List all line items above $1000"
- "Calculate the average price per unit"

**For Spreadsheets:**
- "Summarize the data by category"
- "What's in column B?"
- "Find all entries where quantity > 10"

**For General Documents:**
- "Summarize this document"
- "Extract all dates mentioned"
- "List the key points"

## Need Help?

If you encounter issues:
1. Check the backend logs for detailed error messages
2. Verify your API keys are correct
3. Ensure the file uploaded successfully
4. Try a different AI provider

---

**Note**: This feature requires active internet connection and valid API keys to function.

