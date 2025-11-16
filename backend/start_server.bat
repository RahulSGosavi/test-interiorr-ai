@echo off
echo Starting backend server on port 8000...
cd /d %~dp0
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
pause

