
@echo off
echo Starting FastAPI server...
cd /d "D:\2Project_Pivate\Secin\Kino_Server"

call venv\Scripts\activate.bat
call pip install -r requirements.txt
call playwright install
pause