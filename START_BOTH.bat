@echo off
echo ========================================
echo  Starting Annotation AI Suite Locally
echo ========================================
echo.

echo [1/2] Starting Backend Server...
cd backend
start "Backend Server" cmd /k "python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload"
cd ..

timeout /t 3 /nobreak >nul

echo [2/2] Starting Frontend Server...
cd frontend
start "Frontend Server" cmd /k "npm start"
cd ..

echo.
echo ========================================
echo  Both servers are starting!
echo ========================================
echo  Backend:  http://localhost:8000/docs
echo  Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to exit this window...
pause >nul

