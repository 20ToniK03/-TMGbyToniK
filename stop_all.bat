@echo off
chcp 65001 >nul
title Остановка всех компонентов

echo ============================================
echo   Остановка Kev + Flask + Telegram Bot
echo ============================================
echo.

echo [1/3] Останавливаю Kev-сервер (порт 8009)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8009" ^| findstr "LISTENING"') do (
    echo    Убиваю PID %%a
    taskkill /F /PID %%a >nul 2>nul
)

echo [2/3] Останавливаю Flask (порт 5000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do (
    echo    Убиваю PID %%a
    taskkill /F /PID %%a >nul 2>nul
)

echo [3/3] Останавливаю Telegram-бота (tmg.py)...
for /f "tokens=2 delims=," %%a in ('wmic process where "name='python.exe'" get processid^,commandline /format:csv ^| findstr /I "tmg.py"') do (
    echo    Убиваю PID %%a
    taskkill /F /PID %%a >nul 2>nul
)

echo.
echo ============================================
echo   Все компоненты остановлены.
echo ============================================
pause