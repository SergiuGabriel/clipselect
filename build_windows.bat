@echo off
REM Rulează O SINGURĂ DATĂ pe un PC cu Python instalat. Rezultă dist\ClipSelect\ClipSelect.exe (merge pe orice PC Windows, fără Python).
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --windowed --name ClipSelect --collect-all imageio_ffmpeg ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtMultimedia app.py
echo.
echo Gata: dist\ClipSelect\ClipSelect.exe
pause
