#!/bin/sh
# macOS / Linux
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --windowed --name ClipSelect --collect-all imageio_ffmpeg \
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick \
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtMultimedia app.py
