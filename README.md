# TMGbyToniK

Telegram-бот собирает сообщения из групп и каналов, классифицирует их локальной моделью Kev (важность, категория, срочность) и показывает в веб-интерфейсе на Flask.

## Возможности

- Автоматический сбор сообщений из всех групп и каналов Telegram
- Скачивание медиа (фото, видео, документы)
- Классификация каждого сообщения локальной моделью Kev: категория (tech / news / finance / spam и другие), важность (0.0 – 1.0), срочность (0.0 – 1.0)
- Веб-интерфейс с двумя видами: слайдер и список
- Фильтры: по группе, медиа, статусу, категории Kev, важности, срочности
- Адаптивный дизайн — работает и на телефоне, и на ПК
- Конфигурация через `.env` — секреты не попадают в репозиторий
- Поддержка прокси (SOCKS5 / HTTP / MTProto) для обхода блокировок

## Требования

| Компонент | Минимум | Рекомендуется |
| :--- | :--- | :--- |
| ОС | Windows 10 / Linux / macOS | Windows 11 |
| Python | 3.10+ | 3.11+ |
| RAM | 4 ГБ | 8+ ГБ |
| Диск | 2 ГБ | 5+ ГБ |
| Интернет | Обязательно для Telegram | — |

Для работы Kev-сервера нужно отдельно установить uv и клонировать репозиторий jaredpalmer/kev.

## Установка

Клонируй репозиторий:

```bash
git clone <URL_РЕПОЗИТОРИЯ>
cd <ИМЯ_ПАПКИ>
Создай .env из шаблона:

bash
copy .env.example .env
Открой .env и заполни своими данными:

env
TG_API_ID=12345678
TG_API_HASH=0123456789abcdef0123456789abcdef
TG_PHONE=+79991234567

PROXY_TYPE=
PROXY_HOST=
PROXY_PORT=
PROXY_USER=
PROXY_PASS=

KEV_BASE_URL=http://127.0.0.1:8009
KEV_MODEL=kev-latest

FLASK_HOST=0.0.0.0
FLASK_PORT=5000
Установи зависимости:

bash
pip install -r requirements.txt
Установи Kev-сервер:

bash
cd ..
git clone https://github.com/jaredpalmer/kev.git
cd kev
uv sync --extra serve
Запуск
Терминал 1 — Kev-сервер:

bash
cd /path/to/kev
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-0.5b --port 8009
Дождись строки Uvicorn running on http://127.0.0.1:8009.

Терминал 2 — Flask (веб-интерфейс):

bash
cd /path/to/kev_client
python main.py
Открой в браузере http://127.0.0.1:5000

Терминал 3 — Telegram-бот:

bash
cd /path/to/kev_client
python tmg.py
При первом запуске Telethon попросит код подтверждения из Telegram. Введи его в терминале. Сессия сохранится в session_name.session, при следующих запусках код не потребуется.

Структура
text
kev_client/
├── main.py                 # Flask-сервер, API, HTML-интерфейс
├── tmg.py                  # Telegram-бот (сборщик сообщений)
├── kev_filter.py           # Клиент Kev (классификация)
├── requirements.txt        # Python-зависимости
├── .env                    # Секреты (НЕ коммитить)
├── .env.example            # Шаблон конфигурации
├── .gitignore              # Список игнорируемых файлов
├── categories.json         # Категории для Kev (создаётся автоматически)
├── telegram_messages.json  # Лента сообщений
├── processed_ids.json      # ID обработанных сообщений
├── media/                  # Скачанные медиа
└── session_name.session    # Сессия Telegram
Настройка категорий
Категории Kev читаются из categories.json. Открой блокнотом и отредактируй:

json
{
  "categories": {
    "tech": "💻 Технологии",
    "news": "📰 Новости",
    "finance": "💰 Финансы",
    "spam": "🚫 Спам",
    "personal": "👤 Личное",
    "other": "📦 Другое"
  }
}
Правила: ключ — латиница без пробелов (crypto, ai, politics), значение — любое отображаемое имя с эмодзи, other обязательно как fallback. После правки перезапусти Flask и бота. Kev автоматически начнёт классифицировать сообщения по новым категориям.

API
Метод	Эндпоинт	Описание
GET	/api/messages?page=1&per_page=20	Сообщения с пагинацией
GET	/api/messages_by_group?chat_id=X	Все сообщения из группы
GET	/api/important?threshold=0.7	Только важные сообщения
GET	/api/kev_categories	Список категорий Kev
GET	/api/stats	Статистика
GET	/api/groups	Список групп
POST	/api/clear	Очистить ленту
POST	/api/clear_media	Очистить папку с медиа
GET	/media/<filename>	Отдать медиафайл
Безопасность
Никогда не выкладывай в публичный репозиторий:

Файл	Почему
.env	API-ключи, телефон, пароли прокси
session_name.session	Ключ доступа к Telegram без пароля
session_name.session-journal	То же самое
telegram_messages.json	Вся переписка из групп
processed_ids.json	ID обработанных сообщений
media/	Личные фото и видео
categories.json	Твои персональные интересы
Все они добавлены в .gitignore.

Если случайно залил в GitHub: заверши все сессии в Telegram через Настройки → Устройства, смени пароль 2FA, удали файлы из репозитория командой git rm --cached <файл>, сделай коммит и пуш. Лучше всего — удалить репозиторий и создать заново, потому что файлы остаются в истории Git.

Прокси
Если Telegram блокируется провайдером — настрой прокси в .env.

SOCKS5:

env
PROXY_TYPE=socks5
PROXY_HOST=185.22.44.11
PROXY_PORT=1080
PROXY_USER=myuser
PROXY_PASS=mypassword
PROXY_RDNS=true
HTTP:

env
PROXY_TYPE=http
PROXY_HOST=185.22.44.11
PROXY_PORT=8080
PROXY_USER=
PROXY_PASS=
MTProto:

env
PROXY_TYPE=mtproto
PROXY_HOST=proxy.example.com
PROXY_PORT=443
PROXY_SECRET=dd887296385103b9cb48ea941f1d0b856e
Если PROXY_TYPE пустой — бот работает напрямую.

Решение проблем
Симптом	Решение
uv: command not found	Добавь путь к папке с uv в PATH
TimeoutError при старте бота	Включи VPN или настрой прокси в .env
ZoneInfoNotFoundError	Установи pip install tzdata
ModuleNotFoundError: fcntl	Ты на Windows — обнови tmg.py до кроссплатформенной версии
Kev не отвечает	Проверь, запущен ли сервер на порту 8009
Порт 5000 занят	Смени FLASK_PORT в .env
Пустые теги Kev	Kev-сервер не запущен или упал. Проверь терминал 1
Permission denied при push	Используй Personal Access Token вместо пароля