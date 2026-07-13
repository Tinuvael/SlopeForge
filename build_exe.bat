@echo off
echo Building SlopeForge...

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

python -m pip install -r requirements.txt
python -m pip install pyinstaller

pyinstaller --clean SlopeForge.spec

echo.
echo Build complete.
pause
