# 🚀 Local Development Setup Guide

This guide will help you run the Annotation AI Suite project on your local machine.

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.11+** - [Download Python](https://www.python.org/downloads/)
- **Node.js 18+** and **npm/yarn** - [Download Node.js](https://nodejs.org/)
- **PostgreSQL** (or use Supabase cloud database) - [Download PostgreSQL](https://www.postgresql.org/download/)

## 🗄️ Database Setup

### Option 1: Use Supabase (Recommended - Cloud Database)

1. Your Supabase database is already configured in `.env`
2. No local database installation needed
3. The connection string is already set up

### Option 2: Use Local PostgreSQL

If you prefer a local database:

1. Install PostgreSQL
2. Create a database:
   ```sql
   CREATE DATABASE annotation_db;
   ```
3. Update `.env` file:
   ```env
   DATABASE_URL=postgresql://postgres:your_password@localhost:5432/annotation_db
   ```

## 🔧 Backend Setup

### Step 1: Navigate to Backend Directory

```bash
cd backend
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Verify .env File

Make sure your `backend/.env` file exists with:

```env
DATABASE_URL=postgresql://postgres:us9sbjiS76flQ4yH@db.pnnvgpfjxflxtosbwhib.supabase.co:5432/postgres

SUPABASE_URL=https://pnnvgpfjxflxtosbwhib.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIzaSy...

SECRET_KEY=your-secret-key-change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=43200
CORS_ORIGINS=*
UPLOAD_DIR=uploads
REACT_APP_BACKEND_URL=http://localhost:8000
```

### Step 5: Create Database Tables

The tables will be created automatically when you start the server for the first time.

### Step 6: Run Backend Server

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

The backend will be running at: **http://localhost:8000**

You can access the API documentation at: **http://localhost:8000/docs**

## 🎨 Frontend Setup

### Step 1: Navigate to Frontend Directory

Open a **new terminal window** and navigate to:

```bash
cd frontend
```

### Step 2: Install Dependencies

```bash
# Using npm
npm install

# OR using yarn (if you have yarn.lock)
yarn install
```

### Step 3: Create Frontend .env File (Optional)

Create `frontend/.env` if you need to override the backend URL:

```env
REACT_APP_BACKEND_URL=http://localhost:8000
```

### Step 4: Run Frontend Development Server

```bash
# Using npm
npm start

# OR using yarn
yarn start
```

The frontend will be running at: **http://localhost:3000**

It will automatically open in your browser.

## ✅ Verify Everything is Working

1. **Backend**: Visit http://localhost:8000/docs - You should see the FastAPI Swagger documentation
2. **Frontend**: Visit http://localhost:3000 - You should see the login page
3. **Database**: The backend will automatically create tables on first run

## 🧪 Testing the Setup

### Test Backend API

1. Open http://localhost:8000/docs
2. Try the `/api/auth/signup` endpoint:
   - Click "Try it out"
   - Enter test data:
     ```json
     {
       "email": "test@example.com",
       "username": "testuser",
       "password": "test123",
       "full_name": "Test User"
     }
     ```
   - Click "Execute"
   - Should return a token and user data

### Test Frontend

1. Open http://localhost:3000
2. Click "Sign Up" to create an account
3. After signing up, you should be redirected to the dashboard

## 📝 Quick Start Commands Summary

### Terminal 1 - Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# OR
source venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2 - Frontend
```bash
cd frontend
npm install
npm start
```

## 🔍 Troubleshooting

### Backend Issues

**Issue: `DATABASE_URL environment variable is not set`**
- Solution: Make sure `.env` file exists in `backend/` directory

**Issue: `ModuleNotFoundError`**
- Solution: Activate virtual environment and run `pip install -r requirements.txt`

**Issue: Port 8000 already in use**
- Solution: Change port: `uvicorn server:app --reload --port 8001`

**Issue: NumPy compatibility errors**
- Solution: Ensure NumPy < 2.0 is installed: `pip install "numpy<2.0.0"`

### Frontend Issues

**Issue: `Cannot connect to backend`**
- Solution: Check that backend is running on http://localhost:8000
- Verify `REACT_APP_BACKEND_URL` in frontend `.env` or backend `.env`

**Issue: `npm install` fails**
- Solution: Try deleting `node_modules` and `package-lock.json`, then run `npm install` again

**Issue: Port 3000 already in use**
- Solution: React will prompt you to use a different port, or set: `PORT=3001 npm start`

### Database Issues

**Issue: Connection refused**
- Solution: Check your Supabase connection string in `.env`
- Verify your Supabase project is active

**Issue: Tables not created**
- Solution: Check backend logs for errors. Tables are created automatically on first server start.

## 🎯 Development Tips

1. **Hot Reload**: Both servers support hot reload - changes will reflect automatically
2. **API Testing**: Use http://localhost:8000/docs for interactive API testing
3. **Logs**: Check terminal output for both backend and frontend for debugging
4. **Database**: Use Supabase dashboard to view your database tables

## 📚 Next Steps

- Read the [API Documentation](http://localhost:8000/docs) to understand available endpoints
- Check `DEPLOYMENT.md` for production deployment instructions
- Review the code structure in `backend/` and `frontend/` directories

---

**Happy Coding! 🚀**

