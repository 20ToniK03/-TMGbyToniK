@echo off
chcp 65001 >nul
title Установка Kev + Telegram Feed

echo ============================================
echo   Установка всех зависимостей
echo ============================================
echo.

REM === Проверка uv ===
where uv >nul 2>nul
if errorlevel 1 (
    echo [!] uv не найден. Устанавливаю...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

REM === Проверка Python ===
python --version >nul 2>nul
if errorlevel 1 (
    echo [ОШИБКА] Python не найден в PATH!
    echo Установи Python 3.10+ с https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python найден.
echo.

REM === Проверка папок ===
if not exist "C:\Users\Антон\Desktop\kev" (
    echo [!] Папка kev не найдена. Клонирую репозиторий...
    cd /d C:\Users\Антон\Desktop
    git clone https://github.com/jaredpalmer/kev.git
)

if not exist "C:\Users\Антон\Desktop\kev_client" (
    echo [ОШИБКА] Папка kev_client не найдена!
    echo Создай её и положи туда файлы: main.py, tmg.py, kev_filter.py, requirements.txt
    pause
    exit /b 1
)

echo [OK] Папки найдены.
echo.

REM === Установка зависимостей для Kev-сервера ===
echo [1/2] Устанавливаю зависимости Kev-сервера...
cd /d C:\Users\Антон\Desktop\kev
uv sync --extra serve
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости Kev.
    pause
    exit /b 1
)
echo.

REM === Установка зависимостей для клиента ===
echo [2/2] Устанавливаю зависимости клиента (Flask, Telethon, typesafe-sdk)...
cd /d C:\Users\Антон\Desktop\kev_client
pip install -r requirements.txt
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости клиента.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Установка завершена успешно!
echo.
echo   Теперь запусти start_all.bat
echo ============================================
pause