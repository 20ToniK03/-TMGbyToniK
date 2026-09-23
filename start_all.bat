@echo off
chcp 65001 >nul
title Kev + Telegram Bot Launcher

echo ============================================
echo   Запуск проекта Kev + Telegram Feed
echo ============================================
echo.

REM === Добавляем uv в PATH на случай, если его нет ===
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

REM ============================================
REM   ПРОВЕРКА 1: Kev-сервер (порт 8009)
REM ============================================
echo [Проверка] Kev-сервер на порту 8009...
netstat -ano | findstr ":8009" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo    [OK] Kev уже запущен, пропускаю.
    set KEK_RUNNING=1
) else (
    echo    [--] Kev не запущен, стартую...
    start "Kev Server" cmd /k "cd /d C:\Users\Антон\Desktop\kev && set PATH=%USERPROFILE%\.local\bin;%PATH% && uv run --extra serve python -m kev.serve --run jaredpalmer/kev-0.5b --port 8009"
    set KEK_RUNNING=0
    echo    Жду 40 секунд, пока Kev поднимется...
    timeout /t 40 /nobreak >nul
)

REM ============================================
REM   ПРОВЕРКА 2: Flask (порт 5000)
REM ============================================
echo.
echo [Проверка] Flask на порту 5000...
netstat -ano | findstr ":5000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo    [OK] Flask уже запущен, пропускаю.
) else (
    echo    [--] Flask не запущен, стартую...
    start "Flask UI" cmd /k "cd /d C:\Users\Антон\Desktop\kev_client && python main.py"
    timeout /t 3 /nobreak >nul
)

REM ============================================
REM   ПРОВЕРКА 3: Telegram-бот (по процессу python + tmg.py)
REM ============================================
echo.
echo [Проверка] Telegram-бот (tmg.py)...
tasklist /FI "IMAGENAME eq python.exe" /FO CSV 2>nul | findstr /I "python.exe" >nul
if not errorlevel 1 (
    echo    [!] Python-процессы уже есть. Проверяю, не запущен ли tmg.py...
    wmic process where "name='python.exe'" get commandline 2>nul | findstr /I "tmg.py" >nul
    if not errorlevel 1 (
        echo    [OK] Telegram-бот уже запущен, пропускаю.
        goto :done
    )
)

echo    [--] Telegram-бот не запущен, стартую...
start "Telegram Bot" cmd /k "cd /d C:\Users\Антон\Desktop\kev_client && python tmg.py"

:done
echo.
echo ============================================
echo   Готово!
echo.
echo   Kev:            http://127.0.0.1:8009
echo   Веб-интерфейс:  http://127.0.0.1:5000
echo   Telegram-бот:   работает в фоне
echo ============================================
echo.
echo   Все окна уже открыты. Повторный запуск
echo   этого скрипта НЕ создаст дубликаты.
echo.
pause