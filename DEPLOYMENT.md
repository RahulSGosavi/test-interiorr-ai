# Deployment Guide

This guide explains how to deploy the Interior Design AI Suite application.

## Architecture

The application uses a **single-server architecture** where:
- The FastAPI backend serves both the API (`/api/*`) and the React frontend (static files)
- Frontend makes API calls to the same domain (no separate frontend server needed)
- Everything runs in a single Docker container

## API URL Configuration

The frontend automatically detects the correct API URL:

### Development Mode
- Frontend runs on `localhost:3000` (React dev server)
- API calls go to `http://localhost:8000/api`
- Backend runs separately on port 8000

### Production Mode (After Deployment)
- Both frontend and backend served from the same domain
- API calls use `window.location.origin + '/api'`
- Example: If deployed at `https://myapp.onrender.com`, API calls go to `https://myapp.onrender.com/api`

### Custom Backend URL (Optional)
Set the `REACT_APP_BACKEND_URL` environment variable to override automatic detection:
```bash
REACT_APP_BACKEND_URL=https://custom-backend.com npm run build
```

## Docker Deployment

### Build the Docker Image
```bash
docker build -t interior-ai-suite .
```

### Run the Container
```bash
docker run -p 8000:8000 \
  -e SECRET_KEY="your-secret-key-here" \
  -e DATABASE_URL="sqlite:///./interior_ai.db" \
  -v $(pwd)/data:/app/backend/uploads \
  interior-ai-suite
```

### Environment Variables

Required:
- `SECRET_KEY` - JWT secret key for authentication
- `DATABASE_URL` - Database connection string (default: SQLite)

Optional:
- `PORT` - Server port (default: 8000)
- `CORS_ORIGINS` - Comma-separated allowed origins (default: *)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiry time (default: 43200 = 30 days)

## Platform-Specific Deployment

### Render.com
1. Connect your GitHub repository
2. Choose "Docker" as the environment
3. Set environment variables in the Render dashboard
4. Deploy!

The Dockerfile is already configured for Render deployment.

### Railway.app
1. Connect your GitHub repository
2. Railway auto-detects the Dockerfile
3. Set environment variables
4. Deploy!

### AWS/GCP/Azure
1. Build the Docker image
2. Push to container registry (ECR, GCR, ACR)
3. Deploy to container service (ECS, Cloud Run, Container Instances)
4. Configure load balancer and SSL

## Local Development

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm start
```

The frontend dev server will proxy API requests to `localhost:8000`.

## Verifying Deployment

After deployment, check:
1. Visit your app URL - you should see the login page
2. Open browser DevTools → Network tab
3. Try to login
4. API calls should go to `https://your-domain.com/api/auth/login` (NOT localhost)

## Troubleshooting

### Issue: "ERR_CONNECTION_REFUSED" or calls to localhost in production

**Cause**: Frontend is trying to connect to localhost instead of the deployed backend.

**Solution**: 
1. Ensure you're building with `NODE_ENV=production`
2. Rebuild the Docker image
3. Redeploy

### Issue: CORS errors in production

**Cause**: Backend CORS settings blocking requests.

**Solution**: Set `CORS_ORIGINS` environment variable to your frontend domain:
```bash
CORS_ORIGINS=https://myapp.onrender.com
```

### Issue: 404 on page refresh

**Cause**: React Router needs server-side handling.

**Solution**: Already handled in `backend/server.py` - it serves `index.html` for all non-API routes.

## Security Recommendations

1. **Use a strong SECRET_KEY**: Generate with `openssl rand -hex 32`
2. **Use PostgreSQL in production**: SQLite is for development only
3. **Enable HTTPS**: Use platform's SSL or configure reverse proxy
4. **Set CORS_ORIGINS**: Restrict to your actual domain
5. **Regular backups**: Backup your database and uploads directory

## Database Migration to PostgreSQL

For production, use PostgreSQL instead of SQLite:

1. Create a PostgreSQL database
2. Set `DATABASE_URL` environment variable:
```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname
```
3. Deploy - tables will be created automatically

## Monitoring

Consider adding:
- Application monitoring (Sentry, New Relic)
- Log aggregation (Papertrail, Loggly)
- Uptime monitoring (UptimeRobot, Pingdom)
- Performance monitoring (Datadog, AppDynamics)
