@echo off
chcp 65001 >nul

start "Kev Server" cmd /k "cd /d %~dp0..\kev && set PATH=%USERPROFILE%\.local\bin;%PATH% && uv run --extra serve python -m kev.serve --run jaredpalmer/kev-0.5b --port 8009"
timeout /t 15 /nobreak >nul

start "Flask UI" cmd /k "cd /d %~dp0 && python main.py"
timeout /t 3 /nobreak >nul

start "Telegram Bot" cmd /k "cd /d %~dp0 && python tmg.py"