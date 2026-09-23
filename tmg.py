from telethon import TelegramClient, events
import json
import os
import sys
import datetime
import asyncio
import base64
import mimetypes
import tempfile
import uuid
import html as html_module
from contextlib import contextmanager
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Кроссплатформенная блокировка файлов
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    import msvcrt

from kev_filter import classify_message

# Настройка часового пояса
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# --- Секреты из .env ---
api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")
phone_number = os.getenv("TG_PHONE")


def build_proxy():
    """
    Собирает proxy-параметры из .env.
    Возвращает dict с kwargs для TelegramClient.
    Если PROXY_TYPE пустой — возвращает {} (без прокси).
    """
    proxy_type = (os.getenv("PROXY_TYPE") or "").strip().lower()

    if not proxy_type:
        return {}

    host = os.getenv("PROXY_HOST", "").strip()
    port_str = os.getenv("PROXY_PORT", "").strip()
    user = os.getenv("PROXY_USER", "").strip()
    password = os.getenv("PROXY_PASS", "").strip()
    rdns_str = os.getenv("PROXY_RDNS", "true").strip().lower()
    rdns = rdns_str in ("1", "true", "yes", "on")

    if not host or not port_str:
        print("[WARN] PROXY_TYPE указан, но PROXY_HOST или PROXY_PORT пусты. Работаю без прокси.")
        return {}

    try:
        port = int(port_str)
    except ValueError:
        print(f"[WARN] PROXY_PORT='{port_str}' не число. Работаю без прокси.")
        return {}

    # --- MTProto ---
    if proxy_type == "mtproto":
        from telethon import connection as _conn
        secret = os.getenv("PROXY_SECRET", "").strip()
        if not secret:
            print("[WARN] PROXY_TYPE=mtproto, но PROXY_SECRET пуст. Работаю без прокси.")
            return {}
        print(f"[INFO] Прокси: MTProto {host}:{port}")
        return {
            "connection": _conn.ConnectionTcpMTProxyRandomizedIntermediate,
            "proxy": (host, port, secret),
        }

    # --- SOCKS5 / HTTP ---
    if proxy_type in ("socks5", "http"):
        proxy_tuple = (proxy_type, host, port, rdns, user, password)
        print(f"[INFO] Прокси: {proxy_type.upper()} {host}:{port} (user={user or 'нет'})")
        return {"proxy": proxy_tuple}

    print(f"[WARN] Неизвестный PROXY_TYPE='{proxy_type}'. Работаю без прокси.")
    return {}


# --- Создаём клиент с учётом прокси из .env ---
_proxy_kwargs = build_proxy()

client = TelegramClient(
    "session_name",
    api_id,
    api_hash,
    **_proxy_kwargs
)

# --- Остальные настройки из .env ---
BASE_DIR = Path(__file__).resolve().parent
MESSAGES_FILE = BASE_DIR / "telegram_messages.json"
PROCESSED_IDS_FILE = BASE_DIR / "processed_ids.json"
MEDIA_DIR = BASE_DIR / "media"
DATA_LOCK_FILE = BASE_DIR / ".telegram_data.lock"

# Таймаут для обработки одного сообщения (в секундах)
MESSAGE_TIMEOUT = int(os.getenv("MESSAGE_TIMEOUT", "5"))

# Интервал перезапуска (в секундах)
RESTART_INTERVAL = int(os.getenv("RESTART_INTERVAL", "600"))

# Максимум сообщений в ленте
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "500"))


def log(message, level="INFO"):
    """Функция для логирования с временной меткой"""
    moscow_now = datetime.datetime.now(MOSCOW_TZ)
    timestamp = moscow_now.strftime("%Y-%m-%d %H:%M:%S")

    level_colors = {
        "INFO": "INFO",
        "SUCCESS": "OK",
        "WARNING": "WARN",
        "ERROR": "ERROR",
        "DEBUG": "DEBUG",
        "LOADING": "LOAD",
        "SAVING": "SAVE",
        "SKIP": "SKIP",
    }

    level_text = level_colors.get(level, "INFO")
    print(f"[{timestamp}]\t[{level_text}]\t{message}")


@contextmanager
def data_lock():
    """Блокирует общие файлы ленты для веб-приложения и бота."""
    DATA_LOCK_FILE.touch(exist_ok=True)
    with DATA_LOCK_FILE.open("r+", encoding="utf-8") as lock_file:
        if HAS_FCNTL:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        else:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if HAS_FCNTL:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            else:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


def _atomic_write_json(file_path, data):
    """Записывает JSON во временный файл и заменяет целевой атомарно."""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(data, temp_file, ensure_ascii=False, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, file_path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def _read_json_unlocked(file_path, default):
    file_path = Path(file_path)
    if not file_path.exists():
        return default

    try:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, UnicodeDecodeError, MemoryError, OSError) as error:
        log(f"Ошибка при чтении {file_path.name}: {error}", "ERROR")
        backup_path = file_path.with_name(
            f"{file_path.name}.backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        try:
            file_path.replace(backup_path)
            log(f"Резервная копия сохранена: {backup_path.name}", "WARNING")
        except OSError as backup_error:
            log(f"Не удалось сохранить резервную копию: {backup_error}", "ERROR")
        _atomic_write_json(file_path, default)
        return default


def safe_load_json(file_path, default=None):
    """Безопасно загружает JSON, возвращает default при ошибке"""
    if default is None:
        default = [] if "messages" in str(file_path) else {"processed_ids": []}
    with data_lock():
        return _read_json_unlocked(file_path, default)


def init_json_file():
    log("Инициализация JSON файлов...", "INFO")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    safe_load_json(MESSAGES_FILE, [])
    safe_load_json(PROCESSED_IDS_FILE, {"processed_ids": []})
    log("Инициализация завершена", "SUCCESS")


def get_all_messages():
    messages = safe_load_json(MESSAGES_FILE, [])
    return messages if isinstance(messages, list) else []


def save_message(message_data):
    try:
        with data_lock():
            messages = _read_json_unlocked(MESSAGES_FILE, [])
            if not isinstance(messages, list):
                messages = []
            messages.append(message_data)
            messages = messages[-MAX_MESSAGES:]
            _atomic_write_json(MESSAGES_FILE, messages)
        return True
    except Exception as e:
        log(f"Ошибка при сохранении сообщения: {e}", "ERROR")
        return False


def save_processed_id(message_id):
    try:
        with data_lock():
            data = _read_json_unlocked(PROCESSED_IDS_FILE, {"processed_ids": []})
            if not isinstance(data, dict) or not isinstance(
                data.get("processed_ids"), list
            ):
                data = {"processed_ids": []}
            if message_id in data["processed_ids"]:
                return False
            data["processed_ids"].append(message_id)
            data["processed_ids"] = data["processed_ids"][-10000:]
            _atomic_write_json(PROCESSED_IDS_FILE, data)
            return True
    except Exception as e:
        log(f"Ошибка при сохранении ID: {e}", "ERROR")
        return False


def is_processed(message_id):
    try:
        data = safe_load_json(PROCESSED_IDS_FILE, {"processed_ids": []})
        if not isinstance(data, dict):
            return False
        return message_id in data["processed_ids"]
    except (KeyError, TypeError):
        return False


def get_processed_count():
    try:
        data = safe_load_json(PROCESSED_IDS_FILE, {"processed_ids": []})
        if not isinstance(data, dict):
            return 0
        return len(data["processed_ids"])
    except (KeyError, TypeError):
        return 0


def clear_messages():
    """Очищает ленту атомарно, не оставляя поврежденный JSON."""
    with data_lock():
        _atomic_write_json(MESSAGES_FILE, [])
    log("Лента сообщений очищена", "WARNING")


def is_group_chat(chat_obj):
    """Проверка, является ли чат группой или каналом (НЕ личным чатом)"""
    try:
        if hasattr(chat_obj, "chat"):
            chat = chat_obj.chat
        else:
            chat = chat_obj

        if hasattr(chat, "id"):
            if chat.id > 0:
                return False
            elif chat.id < 0:
                return True

        if hasattr(chat, "broadcast") and chat.broadcast:
            return True

        if hasattr(chat, "megagroup") and chat.megagroup:
            return True

        return False
    except:
        return False


async def process_media(event, message_data):
    """Обрабатывает медиа из сообщения с таймаутом"""
    if not event.message.media:
        return

    try:
        media_bytes = await asyncio.wait_for(
            event.message.download_media(file=bytes), timeout=MESSAGE_TIMEOUT
        )

        if media_bytes:
            if len(media_bytes) > 5 * 1024 * 1024:
                message_data["has_media"] = True
                message_data["message"] = "📎 Медиа (слишком большое)"
                return

            media_type = None
            mime_type = None

            if event.message.photo:
                media_type = "photo"
                mime_type = "image/jpeg"
                message_data["has_media"] = True
                if not message_data["message"]:
                    message_data["message"] = "📷 Фото"
            elif event.message.video:
                media_type = "video"
                mime_type = "video/mp4"
                message_data["has_media"] = True
                if not message_data["message"]:
                    message_data["message"] = "🎥 Видео"
            elif event.message.document:
                media_type = "document"
                mime_type = "application/octet-stream"
                message_data["has_media"] = True
                if not message_data["message"]:
                    if hasattr(event.message.media.document, "attributes"):
                        for attr in event.message.media.document.attributes:
                            if hasattr(attr, "file_name") and attr.file_name:
                                message_data["message"] = f"📎 {attr.file_name}"
                                break
                    if not message_data["message"]:
                        message_data["message"] = "📎 Документ"

            if media_type and mime_type:
                MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                extension = mimetypes.guess_extension(mime_type) or ".bin"
                filename = (
                    f"{message_data['chat_id']}_{message_data['message_id']}_"
                    f"{uuid.uuid4().hex[:10]}{extension}"
                )
                media_path = MEDIA_DIR / filename
                with media_path.open("wb") as media_file:
                    media_file.write(media_bytes)
                message_data["media"].append(
                    {
                        "type": media_type,
                        "mime_type": mime_type,
                        "filename": filename,
                        "url": f"/media/{filename}",
                    }
                )
    except asyncio.TimeoutError:
        log(
            f"Таймаут при скачивании медиа для сообщения ID={message_data.get('message_id')}",
            "WARNING",
        )
        message_data["has_media"] = True
        message_data["message"] = "📎 Медиа (таймаут)"
    except Exception as e:
        pass


def escape_html_text(text):
    """Экранирует HTML специальные символы"""
    return html_module.escape(text)


def convert_entities_to_html(text, entities):
    """Конвертирует entities Telegram в HTML с ссылками"""
    if not text or not entities:
        return escape_html_text(text) if text else ""

    sorted_entities = sorted(entities, key=lambda e: e.offset)
    html_parts = []
    last_end = 0

    for entity in sorted_entities:
        if entity.offset > last_end:
            html_parts.append(escape_html_text(text[last_end : entity.offset]))

        entity_text = text[entity.offset : entity.offset + entity.length]

        if hasattr(entity, "url") and entity.url:
            url = entity.url
            url_escaped = (
                url.replace("&", "&amp;")
                .replace('"', "&quot;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            html_parts.append(
                f'<a href="{url_escaped}" target="_blank" rel="noopener noreferrer">{escape_html_text(entity_text)}</a>'
            )
        elif hasattr(entity, "username") and entity.username:
            html_parts.append(
                f'<a href="https://t.me/{escape_html_text(entity.username)}" target="_blank" rel="noopener noreferrer">{escape_html_text(entity_text)}</a>'
            )
        elif hasattr(entity, "phone") and entity.phone:
            html_parts.append(
                f'<a href="tel:{escape_html_text(entity.phone)}">{escape_html_text(entity_text)}</a>'
            )
        elif hasattr(entity, "email") and entity.email:
            html_parts.append(
                f'<a href="mailto:{escape_html_text(entity.email)}">{escape_html_text(entity_text)}</a>'
            )
        elif hasattr(entity, "mention") and entity.mention:
            username = entity_text.lstrip("@")
            html_parts.append(
                f'<a href="https://t.me/{escape_html_text(username)}" target="_blank" rel="noopener noreferrer">{escape_html_text(entity_text)}</a>'
            )
        elif hasattr(entity, "hashtag") and entity.hashtag:
            hashtag = entity_text.lstrip("#")
            html_parts.append(
                f'<a href="https://t.me/hashtag/{escape_html_text(hashtag)}" target="_blank" rel="noopener noreferrer">{escape_html_text(entity_text)}</a>'
            )
        else:
            html_parts.append(escape_html_text(entity_text))

        last_end = entity.offset + entity.length

    if last_end < len(text):
        html_parts.append(escape_html_text(text[last_end:]))

    return "".join(html_parts)


async def process_message(
    event, from_history=False, force=False, skip_group_check=False
):
    """Обрабатывает одно сообщение с таймаутом"""
    try:
        if not skip_group_check and not is_group_chat(event):
            return False

        msg_id = event.message.id
        if not force and is_processed(msg_id):
            return False

        sender_username = None
        sender_first_name = ""
        sender_id = 0

        try:
            if hasattr(event.message, "sender_id") and event.message.sender_id:
                sender_id = event.message.sender_id
            if hasattr(event.message, "sender") and event.message.sender:
                sender = event.message.sender
                sender_username = (
                    sender.username if hasattr(sender, "username") else None
                )
                sender_first_name = (
                    sender.first_name if hasattr(sender, "first_name") else ""
                )
        except:
            pass

        message_text = event.message.message or ""

        message_html = ""
        try:
            if event.message.entities:
                message_html = convert_entities_to_html(
                    message_text, event.message.entities
                )
            else:
                message_html = escape_html_text(message_text)
        except:
            message_html = escape_html_text(message_text)

        timestamp = ""
        try:
            if event.message.date:
                moscow_time = event.message.date.astimezone(MOSCOW_TZ)
                timestamp = moscow_time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                moscow_now = datetime.datetime.now(MOSCOW_TZ)
                timestamp = moscow_now.strftime("%Y-%m-%d %H:%M:%S")
        except:
            moscow_now = datetime.datetime.now(MOSCOW_TZ)
            timestamp = moscow_now.strftime("%Y-%m-%d %H:%M:%S")

        chat_title = "Группа"
        chat_id = 0
        try:
            if hasattr(event, "chat") and event.chat:
                if hasattr(event.chat, "title") and event.chat.title:
                    chat_title = event.chat.title[:30]
                chat_id = event.chat.id if hasattr(event.chat, "id") else 0
        except:
            pass

        message_data = {
            "message_id": msg_id,
            "sender_id": sender_id,
            "sender_username": sender_username,
            "sender_first_name": sender_first_name,
            "message": message_text,
            "message_html": message_html,
            "timestamp": timestamp,
            "chat_title": chat_title,
            "chat_id": chat_id,
            "media": [],
            "has_media": False,
            "from_history": from_history,
            "processed": True,
        }

        if event.message.media:
            await process_media(event, message_data)

        # --- Kev-классификация ---
        if message_text and message_text.strip():
            kev_result = classify_message(message_text)
            message_data.update(kev_result)
        else:
            message_data.update({
                "kev_important": None,
                "kev_category": None,
                "kev_urgency": None,
                "kev_error": "no_text",
            })
        # --- /Kev-классификация ---

        save_message(message_data)
        save_processed_id(msg_id)

        return True

    except Exception as e:
        log(f"Ошибка при обработке сообщения: {e}", "ERROR")
        return False


async def get_all_groups():
    """Получает список всех групп и каналов из диалогов"""
    try:
        dialogs = await client.get_dialogs()
        groups = []
        for dialog in dialogs:
            if is_group_chat(dialog):
                chat = dialog.entity
                group_info = {
                    "chat_id": chat.id if hasattr(chat, "id") else 0,
                    "title": dialog.title or "Группа",
                    "unread_count": dialog.unread_count or 0,
                }
                groups.append(group_info)
        log(f"Найдено групп и каналов: {len(groups)}", "SUCCESS")
        return groups
    except Exception as e:
        log(f"Ошибка при получении списка групп: {e}", "ERROR")
        return []


async def load_group_unread_all(chat_id):
    """Загружает сообщения из конкретной группы, которых еще нет в JSON"""
    try:
        existing_messages = get_all_messages()
        existing_ids = set()
        for msg in existing_messages:
            if isinstance(msg, dict) and "message_id" in msg:
                existing_ids.add(msg["message_id"])

        dialogs = await client.get_dialogs()
        target_dialog = None

        for dialog in dialogs:
            if is_group_chat(dialog):
                chat = dialog.entity
                if hasattr(chat, "id") and chat.id == chat_id:
                    target_dialog = dialog
                    break

        if not target_dialog:
            log(f"Группа с ID {chat_id} не найдена", "ERROR")
            return 0

        chat_title = target_dialog.title or "Группа"
        unread_count = max(0, int(target_dialog.unread_count or 0))
        load_count = min(100, max(unread_count, 50))

        log(f"Скачивание из '{chat_title}' ({load_count} сообщений)...", "LOADING")

        messages = await client.get_messages(
            target_dialog.entity,
            limit=load_count,
        )

        loaded = 0
        skipped = 0
        for msg in messages:
            if msg.action:
                continue

            if msg.id in existing_ids:
                skipped += 1
                continue

            class MockEvent:
                def __init__(self, msg, chat):
                    self.message = msg
                    self.chat = chat

                async def get_sender(self):
                    return None

            event = MockEvent(msg, target_dialog.entity)

            if await process_message(
                event, from_history=True, force=True, skip_group_check=True
            ):
                loaded += 1
                existing_ids.add(msg.id)

        log(f"'{chat_title}': скачано {loaded}, пропущено {skipped}", "SUCCESS")
        return loaded

    except Exception as e:
        log(f"Ошибка при загрузке: {e}", "ERROR")
        return 0


async def load_history(force_reload=False):
    """Загружает сообщения при запуске"""
    log("Загрузка сообщений...", "INFO")

    existing_messages = get_all_messages()
    existing_ids = set()
    for msg in existing_messages:
        if isinstance(msg, dict) and "message_id" in msg:
            existing_ids.add(msg["message_id"])

    dialogs = await client.get_dialogs()
    groups_to_load = []

    for dialog in dialogs:
        if is_group_chat(dialog):
            groups_to_load.append(dialog)

    total_loaded = 0
    total_skipped = 0

    for dialog in groups_to_load:
        chat_title = dialog.title or "Группа"
        unread_count = max(0, int(dialog.unread_count or 0))
        load_count = unread_count if unread_count > 0 else 20

        log(f"Скачивание из '{chat_title}' ({load_count} сообщений)...", "LOADING")

        try:
            messages = await client.get_messages(
                dialog.entity,
                limit=load_count,
            )

            loaded = 0
            skipped = 0
            for msg in messages:
                if msg.action:
                    continue

                if msg.id in existing_ids:
                    skipped += 1
                    continue

                class MockEvent:
                    def __init__(self, msg, chat):
                        self.message = msg
                        self.chat = chat

                    async def get_sender(self):
                        return None

                event = MockEvent(msg, dialog.entity)

                if await process_message(
                    event, from_history=True, force=True, skip_group_check=True
                ):
                    loaded += 1
                    existing_ids.add(msg.id)

            total_loaded += loaded
            total_skipped += skipped
            log(f"'{chat_title}': скачано {loaded}, пропущено {skipped}", "SUCCESS")

        except Exception as e:
            log(f"'{chat_title}': ошибка - {e}", "ERROR")

    log(f"Итого: скачано {total_loaded}, пропущено {total_skipped}", "SUCCESS")
    print("\t" + "-" * 50)


def cleanup_old_messages():
    """Очищает старые сообщения, оставляя только последние MAX_MESSAGES"""
    try:
        messages = get_all_messages()
        if len(messages) > MAX_MESSAGES:
            messages = messages[-MAX_MESSAGES:]
            with data_lock():
                _atomic_write_json(MESSAGES_FILE, messages)
            log(f"Очищено: осталось {len(messages)} сообщений", "WARNING")
    except Exception as e:
        log(f"Ошибка при очистке: {e}", "ERROR")


async def main():
    log("Запуск Telegram бота", "INFO")
    init_json_file()
    cleanup_old_messages()

    await client.start(phone=phone_number)
    log("Авторизация успешна", "SUCCESS")

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        await process_message(event, from_history=False, skip_group_check=False)

    await load_history(force_reload=True)

    log("Ожидание новых сообщений из групп и каналов...", "INFO")

    bot_task = asyncio.create_task(client.run_until_disconnected())

    while True:
        await asyncio.sleep(RESTART_INTERVAL)
        log("Перезапуск бота...", "WARNING")
        bot_task.cancel()
        await client.disconnect()
        os.execv(sys.executable, ["python"] + sys.argv)


if __name__ == "__main__":
    asyncio.run(main())