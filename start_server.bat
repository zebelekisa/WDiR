@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==========================================================
echo  Zona Orsay Telegram Server v0.5.3
echo ==========================================================
echo.

if not exist telegram_config.py (
  echo Creating Telegram configuration...
  >telegram_config.py echo BOT_TOKEN = ""
  >>telegram_config.py echo ALLOWED_CHAT_ID = ""
  >>telegram_config.py echo POLL_TIMEOUT = 25
)

findstr /C:"PASTE_YOUR_BOT_TOKEN_HERE" telegram_config.py >nul 2>nul
if %errorlevel%==0 goto :configure
findstr /C:"BOT_TOKEN = """ telegram_config.py >nul 2>nul
if %errorlevel%==0 goto :configure
goto :start

:configure
echo Telegram bot is not configured.
echo.
echo Get the token from Telegram @BotFather using /newbot.
echo Example: 123456789:AAExampleToken...
echo.
set /p TOKEN=Paste BotFather token here: 
if "%TOKEN%"=="" (
  echo.
  echo No token entered. Telegram remains disabled.
  echo Run this file again after obtaining the token.
  pause
  exit /b 1
)
>telegram_config.py echo BOT_TOKEN = "%TOKEN%"
>>telegram_config.py echo ALLOWED_CHAT_ID = ""
>>telegram_config.py echo POLL_TIMEOUT = 25
echo.
echo Telegram token saved to telegram_config.py
echo.

:start
python server.py
pause
