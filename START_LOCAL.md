# 🚀 Quick Start - Run Locally

## The Problem
Your frontend (running at `localhost:3000`) is trying to connect to backend at `localhost:8000`, but the backend is not running locally.

## Solution: Start Backend Locally

### Step 1: Open a NEW Terminal Window

### Step 2: Navigate to Backend
```bash
cd backend
```

### Step 3: Activate Virtual Environment
```bash
# Windows PowerShell
.\venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### Step 4: Start Backend Server
```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

### Step 5: Keep This Terminal Running

Now your frontend should connect successfully!

---

## Alternative: Point Frontend to Deployed Backend

If you don't want to run backend locally, create `frontend/.env.local`:

```env
REACT_APP_BACKEND_URL=https://your-deployed-backend-url.com
```

Then restart your frontend:
```bash
npm start
```

---

## Check if Backend is Running

Open: http://localhost:8000/docs

If you see the API documentation, backend is running! ✅

---

## Full Setup (Both Frontend & Backend)

### Terminal 1 - Backend
```bash
cd backend
venv\Scripts\activate          # Windows
# OR
source venv/bin/activate       # Mac/Linux

uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2 - Frontend  
```bash
cd frontend
npm start
```

---

## Still Getting Errors?

### 1. Check if backend .env file exists
```bash
# Should be at: backend/.env
# Should contain: DATABASE_URL, SECRET_KEY, etc.
```

### 2. Install backend dependencies if needed
```bash
cd backend
pip install -r requirements.txt
```

### 3. Check if port 8000 is already in use
```powershell
# Windows PowerShell
netstat -ano | findstr :8000

# If port is in use, kill the process or use different port:
uvicorn server:app --reload --port 8001
```

---

**Happy Coding! 🚀**

