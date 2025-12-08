cls
@echo off
echo Starting FastAPI server...
cd /d "D:\2Project_Pivate\Secin\Kino_Server"

echo Removing __pycache__ directories...
for /d /r %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"

call venv\Scripts\activate.bat
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause