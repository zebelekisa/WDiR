# Zona Orsay Telegram control bot - Python 3, standard library only.
# Commands: /play URL, /stop, /status, /help

import json
import os
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    import telegram_config as cfg
except Exception:
    cfg = None

LOCAL_API = os.environ.get("ZONA_LOCAL_API", "http://127.0.0.1:8765")
BOT_TOKEN = os.environ.get("ZONA_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.environ.get("ZONA_ALLOWED_CHAT_ID", "")
POLL_TIMEOUT = int(os.environ.get("ZONA_TG_POLL_TIMEOUT", "25"))

if not BOT_TOKEN and cfg:
    BOT_TOKEN = getattr(cfg, "BOT_TOKEN", "")
if not ALLOWED_CHAT_ID and cfg:
    ALLOWED_CHAT_ID = str(getattr(cfg, "ALLOWED_CHAT_ID", ""))
if cfg:
    POLL_TIMEOUT = int(getattr(cfg, "POLL_TIMEOUT", POLL_TIMEOUT))

_running = False
_offset = None


def _tg(method, data=None, timeout=35):
    url = "https://api.telegram.org/bot%s/%s" % (BOT_TOKEN, method)
    payload = urlencode(data or {}).encode("utf-8")
    req = Request(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _local(path, data=None):
    url = LOCAL_API + path
    if data is None:
        req = Request(url)
    else:
        payload = urlencode(data).encode("utf-8")
        req = Request(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req, timeout=8) as r:
        raw = r.read().decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except Exception:
            return raw


def _allowed(chat_id):
    # Safe default: if an owner ID is configured, only that chat can control TV.
    return (not ALLOWED_CHAT_ID) or str(chat_id) == str(ALLOWED_CHAT_ID)


def _send(chat_id, text):
    try:
        _tg("sendMessage", {"chat_id": str(chat_id), "text": text})
    except Exception as e:
        print("[Telegram] sendMessage failed:", e)


def _help():
    return (
        "Zona Orsay TV\n\n"
        "/play URL — запустить видео\n"
        "/stop — остановить видео\n"
        "/status — состояние ТВ-сервера\n"
        "/help — эта справка\n\n"
        "URL должен быть прямой ссылкой на MP4/M3U8."
    )


def _handle(msg):
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = str(msg.get("text", "")).strip()
    if chat_id is None or not text:
        return

    if text.startswith("/start"):
        if not ALLOWED_CHAT_ID:
            _send(chat_id, "Бот подключён. Твой Telegram chat_id: %s\n\nДля защиты ТВ добавь его в server/telegram_config.py как ALLOWED_CHAT_ID." % chat_id)
        elif _allowed(chat_id):
            _send(chat_id, "Zona Orsay готов.\n\n" + _help())
        else:
            _send(chat_id, "Доступ запрещён.")
        return

    if not _allowed(chat_id):
        _send(chat_id, "Доступ запрещён. Добавь свой chat_id в ALLOWED_CHAT_ID.")
        return

    if text in ("/help", "/commands"):
        _send(chat_id, _help())
        return

    if text.startswith("/play"):
        url = text[5:].strip()
        if not url:
            _send(chat_id, "Использование:\n/play https://example.com/video.mp4")
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            _send(chat_id, "Нужна ссылка, начинающаяся с http:// или https://")
            return
        try:
            _local("/api/set", {"url": url})
            _send(chat_id, "▶ Отправлено на телевизор\n" + url)
        except Exception as e:
            _send(chat_id, "Ошибка связи с Zona-сервером: %s" % e)
        return

    if text == "/stop":
        try:
            _local("/api/clear", {})
            _send(chat_id, "■ Команда STOP отправлена на телевизор")
        except Exception as e:
            _send(chat_id, "Ошибка связи с Zona-сервером: %s" % e)
        return

    if text == "/status":
        try:
            s = _local("/api/status")
            url = s.get("url", "") if isinstance(s, dict) else ""
            if url:
                _send(chat_id, "TV-сервер: ONLINE\nТекущий URL:\n" + url)
            else:
                _send(chat_id, "TV-сервер: ONLINE\nВидео не задано")
        except Exception as e:
            _send(chat_id, "TV-сервер: OFFLINE\n%s" % e)
        return

    _send(chat_id, "Неизвестная команда.\n\n" + _help())


def _poll_loop():
    global _offset, _running
    print("[Telegram] bot enabled")
    while _running:
        try:
            data = {"timeout": POLL_TIMEOUT, "allowed_updates": json.dumps(["message"])}
            if _offset is not None:
                data["offset"] = _offset
            result = _tg("getUpdates", data, timeout=POLL_TIMEOUT + 10)
            if not result.get("ok"):
                time.sleep(3)
                continue
            for update in result.get("result", []):
                _offset = int(update["update_id"]) + 1
                try:
                    _handle(update.get("message", {}))
                except Exception as e:
                    print("[Telegram] message error:", e)
        except (URLError, HTTPError, TimeoutError, OSError) as e:
            print("[Telegram] connection error:", e)
            time.sleep(5)
        except Exception as e:
            print("[Telegram] error:", e)
            time.sleep(5)


def start():
    global _running
    if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        print("[Telegram] disabled: configure BOT_TOKEN in server/telegram_config.py")
        return None
    if _running:
        return None
    _running = True
    t = threading.Thread(target=_poll_loop, name="ZonaTelegramBot", daemon=True)
    t.start()
    return t


def stop():
    global _running
    _running = False
