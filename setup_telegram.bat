@echo off
cd /d "%~dp0"
echo ================================================
echo Zona Orsay - Telegram setup
 echo ================================================
echo.
echo 1. Open Telegram and talk to @BotFather.
echo 2. Create a bot with /newbot and copy the token.
echo.
set /p TOKEN=Paste BotFather token here: 
if "%TOKEN%"=="" goto :bad
>telegram_config.py echo BOT_TOKEN = "%TOKEN%"
>>telegram_config.py echo ALLOWED_CHAT_ID = ""
>>telegram_config.py echo POLL_TIMEOUT = 25
echo.
echo Configuration saved.
echo Start start_server.bat, then send /start to your bot.
echo The bot will show your chat_id. Put it into telegram_config.py and restart.
pause
exit /b
:bad
echo Token was empty. Nothing changed.
pause
