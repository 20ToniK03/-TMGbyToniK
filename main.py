from flask import Flask, render_template_string, jsonify, request, send_from_directory
import tmg
from kev_filter import get_categories
import json
import os
from dotenv import load_dotenv

load_dotenv()

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

app = Flask(__name__)


@app.route("/api/messages")
def api_messages():
    """API с пагинацией"""
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except (TypeError, ValueError):
        return jsonify(
            {"status": "error", "message": "Некорректные параметры пагинации"}
        ), 400

    messages = tmg.get_all_messages()
    messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    start = (page - 1) * per_page
    end = start + per_page
    paginated = messages[start:end]

    return jsonify(
        {
            "messages": paginated,
            "total": len(messages),
            "page": page,
            "per_page": per_page,
            "total_pages": (len(messages) + per_page - 1) // per_page,
        }
    )


@app.route("/api/messages_by_group")
def api_messages_by_group():
    """API для получения ВСЕХ сообщений из конкретной группы"""
    try:
        chat_id = request.args.get("chat_id")
        if not chat_id:
            return jsonify({"status": "error", "message": "Не указан chat_id"}), 400

        messages = tmg.get_all_messages()
        group_messages = [
            m for m in messages if str(m.get("chat_id", "")) == str(chat_id)
        ]
        group_messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return jsonify(
            {
                "status": "success",
                "messages": group_messages,
                "total": len(group_messages),
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/important")
def api_important():
    """Только сообщения, которые Kev счёл важными."""
    try:
        threshold = float(request.args.get("threshold", 0.7))
    except ValueError:
        threshold = 0.7

    messages = tmg.get_all_messages()
    important = [
        m for m in messages
        if isinstance(m, dict)
        and m.get("kev_important") is not None
        and m.get("kev_important") >= threshold
    ]
    important.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify({"status": "success", "messages": important, "total": len(important)})


@app.route("/api/kev_categories")
def api_kev_categories():
    """Отдаёт список категорий Kev для фронтенда."""
    try:
        categories = get_categories()
        return jsonify({"status": "success", "categories": categories})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    """Статистика"""
    messages = tmg.get_all_messages()
    total = len(messages)
    with_media = len(
        [m for m in messages if m.get("media") and len(m.get("media", [])) > 0]
    )
    from_history = len([m for m in messages if m.get("from_history", False)])
    processed = tmg.get_processed_count()
    kev_classified = len(
        [m for m in messages if m.get("kev_important") is not None]
    )

    return jsonify(
        {
            "total": total,
            "with_media": with_media,
            "from_history": from_history,
            "processed": processed,
            "kev_classified": kev_classified,
        }
    )


@app.route("/api/groups")
def get_groups():
    """Получить список всех групп из JSON"""
    try:
        messages = tmg.get_all_messages()
        groups = {}

        for msg in messages:
            if isinstance(msg, dict) and "chat_id" in msg:
                chat_id = msg["chat_id"]
                chat_title = msg.get("chat_title", "Группа")
                if chat_id not in groups:
                    groups[chat_id] = {
                        "chat_id": chat_id,
                        "title": chat_title,
                        "message_count": 0,
                    }
                groups[chat_id]["message_count"] += 1

        groups_list = list(groups.values())
        return jsonify({"status": "success", "groups": groups_list})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/clear", methods=["POST"])
def clear_messages():
    """Очистить все сообщения"""
    try:
        tmg.clear_messages()
        return jsonify({"status": "success", "message": "Лента очищена"})
    except Exception as e:
        return jsonify({"status": "error", "message": "Не удалось очистить ленту"}), 500


@app.route("/api/clear_media", methods=["POST"])
def clear_media():
    """Очистить папку с медиа"""
    try:
        import shutil

        if tmg.MEDIA_DIR.exists():
            shutil.rmtree(tmg.MEDIA_DIR)
            tmg.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        return jsonify({"status": "success", "message": "Медиа очищена"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/media/<path:filename>")
def media_file(filename):
    """Раздаёт медиа отдельно от JSON-ленты."""
    return send_from_directory(tmg.MEDIA_DIR, filename)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(tmg.BASE_DIR, "generated-icon.png")


@app.route("/")
def index():
    site_text = """
    <!DOCTYPE html>
    <html lang="ru" data-theme="light">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <meta name="theme-color" content="#eef2f9">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="default">
        <title>Telegram Groups Feed</title>
        <script>
            (function() {
                try {
                    var saved = localStorage.getItem('theme');
                    if (saved === 'dark' || saved === 'light') {
                        document.documentElement.setAttribute('data-theme', saved);
                    }
                } catch (e) {}
            })();
        </script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
            html { font-size: 16px; -webkit-text-size-adjust: 100%; }

            /* ============================================
               ПЕРЕМЕННЫЕ ТЕМ
               ============================================ */
            :root, [data-theme="light"] {
                --bg-base: #eef2f9;
                --bg-gradient-1: rgba(167, 139, 250, 0.5);
                --bg-gradient-2: rgba(94, 234, 212, 0.5);
                --bg-gradient-3: rgba(251, 191, 36, 0.2);
                --bg-gradient-end-1: #f7f9fd;
                --bg-gradient-end-2: #eef2f9;
                --grid-color: rgba(0, 0, 0, 0.03);
                --text-primary: #1a2332;
                --text-secondary: #7c8798;
                --text-tertiary: #9aa4b2;
                --panel-bg: rgba(255, 255, 255, 0.5);
                --panel-border: rgba(255, 255, 255, 0.7);
                --panel-shadow: rgba(31, 41, 55, 0.08);
                --panel-inset: rgba(255, 255, 255, 0.9);
                --card-bg: rgba(255, 255, 255, 0.85);
                --card-border: rgba(255, 255, 255, 0.9);
                --card-shadow: rgba(31, 41, 55, 0.06);
                --input-bg: rgba(255, 255, 255, 0.75);
                --input-border: rgba(255, 255, 255, 0.9);
                --input-focus: rgba(255, 255, 255, 0.95);
                --btn-bg: rgba(255, 255, 255, 0.85);
                --btn-border: rgba(255, 255, 255, 0.9);
                --btn-shadow: rgba(31, 41, 55, 0.08);
                --modal-bg: rgba(255, 255, 255, 0.85);
                --modal-overlay: rgba(255, 255, 255, 0.4);
                --modal-overlay-strong: rgba(255, 255, 255, 0.45);
                --message-bg: rgba(255, 255, 255, 0.85);
                --accent-1: #8b5cf6;
                --accent-2: #6366f1;
                --accent-teal: #14b8a6;
                --chat-color: #0d9488;
                --source-color: #7c3aed;
                --border-subtle: rgba(31, 41, 55, 0.08);
                --scroll-thumb-1: rgba(139, 92, 246, 0.5);
                --scroll-thumb-2: rgba(99, 102, 241, 0.5);
            }
            [data-theme="dark"] {
                --bg-base: #070b14;
                --bg-gradient-1: rgba(108, 92, 231, 0.35);
                --bg-gradient-2: rgba(0, 184, 148, 0.28);
                --bg-gradient-3: rgba(255, 118, 117, 0.12);
                --bg-gradient-end-1: #070b14;
                --bg-gradient-end-2: #0a0e1a;
                --grid-color: rgba(255, 255, 255, 0.025);
                --text-primary: #e4e9f2;
                --text-secondary: #7d8ba1;
                --text-tertiary: #6a7a8e;
                --panel-bg: rgba(20, 31, 45, 0.55);
                --panel-border: rgba(255, 255, 255, 0.08);
                --panel-shadow: rgba(0, 0, 0, 0.35);
                --panel-inset: rgba(255, 255, 255, 0.06);
                --card-bg: rgba(10, 14, 26, 0.75);
                --card-border: rgba(255, 255, 255, 0.08);
                --card-shadow: rgba(0, 0, 0, 0.35);
                --input-bg: rgba(10, 14, 26, 0.65);
                --input-border: rgba(255, 255, 255, 0.08);
                --input-focus: rgba(10, 14, 26, 0.85);
                --btn-bg: rgba(10, 14, 26, 0.7);
                --btn-border: rgba(255, 255, 255, 0.08);
                --btn-shadow: rgba(0, 0, 0, 0.3);
                --modal-bg: rgba(20, 31, 45, 0.9);
                --modal-overlay: rgba(3, 6, 14, 0.75);
                --modal-overlay-strong: rgba(3, 6, 14, 0.85);
                --message-bg: rgba(10, 14, 26, 0.75);
                --accent-1: #8b7cf7;
                --accent-2: #6c5ce7;
                --accent-teal: #00b894;
                --chat-color: #00cec9;
                --source-color: #a78bfa;
                --border-subtle: rgba(255, 255, 255, 0.08);
                --scroll-thumb-1: rgba(108, 92, 231, 0.6);
                --scroll-thumb-2: rgba(139, 124, 247, 0.6);
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                color: var(--text-primary);
                padding: 20px;
                min-height: 100vh;
                min-height: 100dvh;
                display: flex;
                justify-content: center;
                align-items: flex-start;
                overflow-x: hidden;
                position: relative;
                background: var(--bg-base);
                transition: background 0.4s ease, color 0.4s ease;
            }
            body::before {
                content: "";
                position: fixed;
                inset: 0;
                z-index: -2;
                background:
                    radial-gradient(1100px 800px at 15% 10%, var(--bg-gradient-1), transparent 60%),
                    radial-gradient(1000px 700px at 85% 85%, var(--bg-gradient-2), transparent 60%),
                    radial-gradient(800px 600px at 50% 50%, var(--bg-gradient-3), transparent 70%),
                    linear-gradient(180deg, var(--bg-gradient-end-1) 0%, var(--bg-gradient-end-2) 100%);
                animation: bgFloat 22s ease-in-out infinite alternate;
                transition: background 0.5s ease;
            }
            body::after {
                content: "";
                position: fixed;
                inset: 0;
                z-index: -1;
                pointer-events: none;
                background-image:
                    linear-gradient(var(--grid-color) 1px, transparent 1px),
                    linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
                background-size: 40px 40px;
                mask-image: radial-gradient(circle at 50% 40%, black 40%, transparent 80%);
                -webkit-mask-image: radial-gradient(circle at 50% 40%, black 40%, transparent 80%);
            }
            @keyframes bgFloat {
                0%   { filter: hue-rotate(0deg)   saturate(1); }
                50%  { filter: hue-rotate(10deg)  saturate(1.05); }
                100% { filter: hue-rotate(-8deg)  saturate(0.95); }
            }
            .container { max-width: 900px; width: 100%; margin: 0 auto; }

            .header {
                display: flex; justify-content: space-between; align-items: center;
                padding: 22px 26px;
                margin-bottom: 22px;
                border-radius: 20px;
                flex-wrap: wrap; gap: 12px;
                background: var(--panel-bg);
                backdrop-filter: blur(24px) saturate(180%);
                -webkit-backdrop-filter: blur(24px) saturate(180%);
                border: 1px solid var(--panel-border);
                box-shadow:
                    0 8px 32px var(--panel-shadow),
                    inset 0 1px 0 var(--panel-inset);
                transition: background 0.4s ease, border 0.4s ease, box-shadow 0.4s ease;
            }
            .header h1 {
                font-size: 24px; font-weight: 700;
                background: linear-gradient(120deg, var(--accent-1) 0%, var(--accent-2) 40%, var(--accent-teal) 100%);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                background-clip: text;
                letter-spacing: -0.3px;
            }
            .header h1 small {
                font-size: 13px; -webkit-text-fill-color: var(--text-secondary);
                background: none; font-weight: 400; margin-left: 6px;
            }
            .header-controls { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

            /* Кнопка темы */
            .theme-toggle {
                width: 44px; height: 44px;
                border-radius: 12px;
                background: var(--btn-bg);
                border: 1px solid var(--btn-border);
                color: var(--text-primary);
                cursor: pointer;
                display: flex; align-items: center; justify-content: center;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                box-shadow:
                    0 4px 14px var(--btn-shadow),
                    inset 0 1px 0 var(--panel-inset);
                position: relative;
                overflow: hidden;
                flex-shrink: 0;
            }
            .theme-toggle:hover {
                transform: translateY(-2px) rotate(12deg);
                border-color: var(--accent-1);
                box-shadow:
                    0 8px 24px rgba(139, 92, 246, 0.3),
                    inset 0 1px 0 var(--panel-inset);
            }
            .theme-toggle:active { transform: translateY(0) scale(0.95); }
            .theme-toggle svg {
                width: 22px; height: 22px;
                transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease;
                position: absolute;
            }
            .theme-toggle .icon-sun {
                opacity: 1;
                transform: rotate(0deg) scale(1);
                color: #f59e0b;
            }
            .theme-toggle .icon-moon {
                opacity: 0;
                transform: rotate(-90deg) scale(0.5);
                color: #6366f1;
            }
            [data-theme="dark"] .theme-toggle .icon-sun {
                opacity: 0;
                transform: rotate(90deg) scale(0.5);
            }
            [data-theme="dark"] .theme-toggle .icon-moon {
                opacity: 1;
                transform: rotate(0deg) scale(1);
            }

            .view-toggle {
                display: flex; gap: 4px;
                background: var(--input-bg);
                padding: 4px; border-radius: 14px;
                border: 1px solid var(--input-border);
                box-shadow:
                    inset 0 1px 2px var(--card-shadow),
                    0 2px 8px var(--card-shadow);
                transition: background 0.4s ease, border 0.4s ease;
            }
            .view-toggle button {
                background: none; border: none; color: var(--text-secondary);
                padding: 8px 18px; border-radius: 10px; cursor: pointer;
                font-size: 13px; font-weight: 600;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                min-height: 40px; display: flex; align-items: center;
                gap: 6px; white-space: nowrap;
            }
            .view-toggle button.active {
                background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
                color: white;
                box-shadow:
                    0 4px 14px rgba(139, 92, 246, 0.35),
                    inset 0 1px 0 rgba(255, 255, 255, 0.3);
            }
            .view-toggle button:hover:not(.active) {
                background: var(--input-focus); color: var(--text-primary);
            }

            .filters {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 10px; margin-bottom: 22px;
                padding: 18px;
                border-radius: 20px;
                background: var(--panel-bg);
                backdrop-filter: blur(24px) saturate(180%);
                -webkit-backdrop-filter: blur(24px) saturate(180%);
                border: 1px solid var(--panel-border);
                box-shadow:
                    0 8px 32px var(--panel-shadow),
                    inset 0 1px 0 var(--panel-inset);
                transition: background 0.4s ease, border 0.4s ease, box-shadow 0.4s ease;
            }
            .filters input, .filters select {
                padding: 12px 16px;
                background: var(--input-bg);
                border: 1px solid var(--input-border);
                border-radius: 12px;
                color: var(--text-primary); font-size: 14px; width: 100%;
                min-height: 44px;
                -webkit-appearance: none; appearance: none;
                transition: all 0.25s ease;
                box-shadow:
                    inset 0 1px 2px var(--card-shadow),
                    0 1px 2px var(--card-shadow);
            }
            .filters input:focus, .filters select:focus {
                outline: none;
                border-color: rgba(139, 92, 246, 0.5);
                box-shadow:
                    inset 0 1px 2px var(--card-shadow),
                    0 0 0 4px rgba(139, 92, 246, 0.15);
                background: var(--input-focus);
            }
            .filters select {
                background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%237c8798' stroke-width='2'%3e%3cpolyline points='6 9 12 15 18 9'/%3e%3c/svg%3e");
                background-repeat: no-repeat;
                background-position: right 12px center;
                background-size: 16px;
                padding-right: 38px;
            }
            .filters input::placeholder { color: var(--text-tertiary); }
            .filters select option { background: var(--bg-gradient-end-1); color: var(--text-primary); }

            .filters .filter-btn {
                padding: 12px 20px;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 12px;
                color: white; cursor: pointer;
                font-size: 14px; font-weight: 600;
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
                min-height: 44px;
                display: flex; align-items: center;
                justify-content: center; gap: 6px; white-space: nowrap;
                background: linear-gradient(135deg, rgba(139, 92, 246, 0.9), rgba(99, 102, 241, 0.9));
                box-shadow:
                    0 4px 14px rgba(139, 92, 246, 0.3),
                    inset 0 1px 0 rgba(255, 255, 255, 0.3);
            }
            .filters .filter-btn:hover {
                transform: translateY(-1px);
                box-shadow:
                    0 8px 24px rgba(139, 92, 246, 0.4),
                    inset 0 1px 0 rgba(255, 255, 255, 0.4);
            }
            .filters .filter-btn:active { transform: translateY(0) scale(0.98); }
            .filters .filter-btn.danger {
                background: linear-gradient(135deg, rgba(248, 113, 113, 0.9), rgba(239, 68, 68, 0.9));
                box-shadow: 0 4px 14px rgba(239, 68, 68, 0.3), inset 0 1px 0 rgba(255,255,255,0.3);
            }
            .filters .filter-btn.danger:hover {
                box-shadow: 0 8px 24px rgba(239, 68, 68, 0.45), inset 0 1px 0 rgba(255,255,255,0.4);
            }
            .filters .filter-btn.success {
                background: linear-gradient(135deg, rgba(52, 211, 153, 0.9), rgba(20, 184, 166, 0.9));
                box-shadow: 0 4px 14px rgba(20, 184, 166, 0.3), inset 0 1px 0 rgba(255,255,255,0.3);
            }
            .filters .filter-btn.success:hover {
                box-shadow: 0 8px 24px rgba(20, 184, 166, 0.45), inset 0 1px 0 rgba(255,255,255,0.4);
            }
            .filters .filter-btn.warning {
                background: linear-gradient(135deg, rgba(251, 191, 36, 0.9), rgba(245, 158, 11, 0.9));
                box-shadow: 0 4px 14px rgba(245, 158, 11, 0.3), inset 0 1px 0 rgba(255,255,255,0.3);
            }
            .filters .filter-btn.warning:hover {
                box-shadow: 0 8px 24px rgba(245, 158, 11, 0.45), inset 0 1px 0 rgba(255,255,255,0.4);
            }

            .slider-container {
                position: relative;
                border-radius: 22px;
                padding: 30px;
                min-height: 300px;
                display: flex; flex-direction: column; justify-content: center;
                background: var(--panel-bg);
                backdrop-filter: blur(24px) saturate(180%);
                -webkit-backdrop-filter: blur(24px) saturate(180%);
                border: 1px solid var(--panel-border);
                box-shadow:
                    0 8px 32px var(--panel-shadow),
                    inset 0 1px 0 var(--panel-inset);
                transition: background 0.4s ease, border 0.4s ease, box-shadow 0.4s ease;
            }
            .slider-progress {
                text-align: center; color: var(--text-secondary);
                font-size: 14px; margin-bottom: 20px;
            }
            .slider-progress strong { color: var(--text-primary); }
            .slider-card { flex: 1; }

            .slider-message {
                background: var(--message-bg);
                border-radius: 16px;
                padding: 26px;
                border: 1px solid var(--card-border);
                min-height: 200px;
                display: flex; flex-direction: column; position: relative;
                cursor: pointer;
                transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
                box-shadow:
                    0 4px 16px var(--card-shadow),
                    inset 0 1px 0 var(--panel-inset);
            }
            .slider-message:hover {
                border-color: rgba(139, 92, 246, 0.4);
                box-shadow:
                    0 12px 40px rgba(139, 92, 246, 0.15),
                    inset 0 1px 0 var(--panel-inset);
                transform: translateY(-2px);
            }
            .slider-message .status-badge {
                position: absolute; top: -10px; right: -10px;
                padding: 4px 12px; border-radius: 20px;
                font-size: 10px; font-weight: 700;
                text-transform: uppercase; letter-spacing: 0.6px;
                box-shadow: 0 4px 12px rgba(31, 41, 55, 0.15);
            }
            .slider-message .status-badge.history {
                background: linear-gradient(135deg, #a78bfa, #8b5cf6);
                color: white;
            }
            .slider-message .status-badge.new {
                background: linear-gradient(135deg, #34d399, #14b8a6);
                color: white;
                animation: pulse 2s infinite;
            }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }

            .message-header {
                display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 14px; font-size: 13px; flex-wrap: wrap; gap: 6px;
            }
            .message-chat { color: var(--chat-color); font-weight: 700; }
            .message-source { color: var(--source-color); font-weight: 700; }
            .message-date { color: var(--text-secondary); font-size: 12px; }

            .slider-message .message-text {
                font-size: 18px; line-height: 1.7;
                margin-bottom: 16px; flex: 1;
                word-wrap: break-word; overflow-wrap: break-word;
                color: var(--text-primary);
            }
            .slider-message .message-text a,
            .list-message .message-text a,
            .modal-message .message-text a {
                color: var(--chat-color); text-decoration: underline;
                word-break: break-all; transition: color 0.3s;
            }
            .slider-message .message-text a:hover,
            .list-message .message-text a:hover,
            .modal-message .message-text a:hover {
                color: var(--accent-teal); text-decoration: none;
            }
            .slider-message .message-text a[href*="t.me"],
            .list-message .message-text a[href*="t.me"],
            .modal-message .message-text a[href*="t.me"] {
                color: var(--source-color);
            }
            .slider-message .message-text a[href*="t.me"]:hover,
            .list-message .message-text a[href*="t.me"]:hover,
            .modal-message .message-text a[href*="t.me"]:hover {
                color: var(--accent-1);
            }

            .message-media {
                display: flex; gap: 10px; flex-wrap: wrap;
                margin: 10px 0; justify-content: center;
            }
            .message-media img, .message-media video {
                max-width: 100%; max-height: 400px;
                border-radius: 12px;
                border: 1px solid var(--card-border);
                height: auto;
                box-shadow: 0 8px 24px var(--card-shadow);
            }
            .message-media video { max-height: 500px; }

            .message-tags {
                display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px;
            }
            .tag {
                padding: 5px 12px; border-radius: 20px;
                font-size: 12px; font-weight: 600;
                white-space: nowrap;
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
            }
            .tag-media { background: rgba(20, 184, 166, 0.12); color: #0d9488; border: 1px solid rgba(20, 184, 166, 0.3); }
            .tag-no-text { background: rgba(245, 158, 11, 0.12); color: #b45309; border: 1px solid rgba(245, 158, 11, 0.3); }
            .tag-photo { background: rgba(139, 92, 246, 0.12); color: #7c3aed; border: 1px solid rgba(139, 92, 246, 0.3); }
            .tag-video { background: rgba(239, 68, 68, 0.12); color: #dc2626; border: 1px solid rgba(239, 68, 68, 0.3); }
            .tag-group { background: rgba(20, 184, 166, 0.12); color: #0d9488; border: 1px solid rgba(20, 184, 166, 0.3); }
            .tag-history { background: rgba(139, 92, 246, 0.12); color: #7c3aed; border: 1px solid rgba(139, 92, 246, 0.3); }
            .tag-processed { background: rgba(20, 184, 166, 0.12); color: #0d9488; border: 1px solid rgba(20, 184, 166, 0.3); }
            .tag-not-downloaded { background: rgba(239, 68, 68, 0.12); color: #dc2626; border: 1px solid rgba(239, 68, 68, 0.3); }
            .tag-kev-cat { background: rgba(139, 92, 246, 0.12); color: #7c3aed; border: 1px solid rgba(139, 92, 246, 0.3); }
            .tag-kev-important { background: rgba(239, 68, 68, 0.12); color: #dc2626; border: 1px solid rgba(239, 68, 68, 0.3); }
            .tag-kev-skip { background: rgba(120, 120, 120, 0.1); color: #6b7280; border: 1px solid rgba(120, 120, 120, 0.25); }
            .tag-kev-urgent { background: rgba(245, 158, 11, 0.12); color: #b45309; border: 1px solid rgba(245, 158, 11, 0.3); }
            .tag-kev-later { background: rgba(20, 184, 166, 0.12); color: #0d9488; border: 1px solid rgba(20, 184, 166, 0.3); }

            .slider-controls {
                display: flex; justify-content: center; gap: 12px;
                margin-top: 22px; flex-wrap: wrap;
            }
            .slider-controls .nav-btn {
                background: var(--btn-bg);
                border: 1px solid var(--btn-border);
                color: var(--text-primary);
                padding: 12px 32px;
                border-radius: 14px; cursor: pointer;
                font-size: 15px; font-weight: 600;
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
                min-width: 130px; min-height: 48px;
                display: flex; align-items: center; justify-content: center;
                box-shadow:
                    0 4px 14px var(--btn-shadow),
                    inset 0 1px 0 var(--panel-inset);
            }
            .slider-controls .nav-btn:hover:not(:disabled) {
                background: linear-gradient(135deg, rgba(139, 92, 246, 0.95), rgba(99, 102, 241, 0.95));
                border-color: rgba(139, 92, 246, 0.5);
                color: white;
                transform: translateY(-1px);
                box-shadow: 0 8px 24px rgba(139, 92, 246, 0.4);
            }
            .slider-controls .nav-btn:active:not(:disabled) { transform: translateY(0) scale(0.98); }
            .slider-controls .nav-btn:disabled { opacity: 0.35; cursor: not-allowed; }

            .list-view { display: none; }
            .list-view.active { display: block; }
            .list-message {
                background: var(--panel-bg);
                backdrop-filter: blur(24px) saturate(180%);
                -webkit-backdrop-filter: blur(24px) saturate(180%);
                border-radius: 18px;
                padding: 22px;
                margin-bottom: 16px;
                border: 1px solid var(--panel-border);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative; cursor: pointer;
                box-shadow:
                    0 8px 32px var(--panel-shadow),
                    inset 0 1px 0 var(--panel-inset);
            }
            .list-message:hover {
                border-color: rgba(139, 92, 246, 0.4);
                transform: translateY(-3px);
                box-shadow:
                    0 16px 44px rgba(139, 92, 246, 0.18),
                    inset 0 1px 0 var(--panel-inset);
            }
            .list-message .status-badge {
                position: absolute; top: -8px; right: -8px;
                padding: 3px 10px; border-radius: 20px;
                font-size: 9px; font-weight: 700;
                text-transform: uppercase; letter-spacing: 0.5px;
                box-shadow: 0 4px 12px rgba(31, 41, 55, 0.15);
            }
            .list-message .status-badge.history {
                background: linear-gradient(135deg, #a78bfa, #8b5cf6);
                color: white;
            }
            .list-message .status-badge.new {
                background: linear-gradient(135deg, #34d399, #14b8a6);
                color: white; animation: pulse 2s infinite;
            }
            .list-message .message-text {
                font-size: 15px; line-height: 1.6;
                margin-bottom: 12px;
                word-wrap: break-word; overflow-wrap: break-word;
                color: var(--text-primary);
            }
            .list-message .message-media img,
            .list-message .message-media video {
                max-width: 200px; max-height: 150px;
                border-radius: 12px;
                border: 1px solid var(--card-border);
                object-fit: cover;
                box-shadow: 0 6px 18px var(--card-shadow);
            }

            .empty-state {
                text-align: center; padding: 60px 20px; color: var(--text-secondary);
            }
            .empty-state .icon { font-size: 56px; margin-bottom: 20px; opacity: 0.6; }

            .confirm-modal {
                display: none; position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: var(--modal-overlay);
                backdrop-filter: blur(12px) saturate(180%);
                -webkit-backdrop-filter: blur(12px) saturate(180%);
                z-index: 1000;
                justify-content: center; align-items: center;
                padding: 20px;
            }
            .confirm-modal.active { display: flex; }
            .confirm-modal .modal-content {
                background: var(--modal-bg);
                backdrop-filter: blur(40px) saturate(180%);
                -webkit-backdrop-filter: blur(40px) saturate(180%);
                padding: 32px; border-radius: 22px;
                border: 1px solid var(--panel-border);
                max-width: 420px; width: 100%; text-align: center;
                box-shadow:
                    0 24px 60px var(--panel-shadow),
                    inset 0 1px 0 var(--panel-inset);
            }
            .confirm-modal .modal-content h3 {
                margin-bottom: 15px;
                background: linear-gradient(135deg, #f87171, #ef4444);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                background-clip: text;
                font-size: 20px;
                font-weight: 700;
            }
            .confirm-modal .modal-content p { margin-bottom: 22px; color: var(--text-secondary); }
            .confirm-modal .modal-buttons { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
            .confirm-modal .modal-buttons button {
                padding: 12px 30px; border: none; border-radius: 12px;
                cursor: pointer; font-size: 14px; font-weight: 600;
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
                min-height: 44px; flex: 1; min-width: 120px;
            }
            .confirm-modal .modal-buttons .confirm-yes {
                background: linear-gradient(135deg, #ef4444, #f87171);
                color: white;
                box-shadow: 0 4px 14px rgba(239, 68, 68, 0.3);
            }
            .confirm-modal .modal-buttons .confirm-yes:hover {
                transform: translateY(-1px);
                box-shadow: 0 8px 24px rgba(239, 68, 68, 0.45);
            }
            .confirm-modal .modal-buttons .confirm-no {
                background: var(--btn-bg);
                color: var(--text-primary);
                border: 1px solid var(--btn-border);
                box-shadow: 0 4px 14px var(--btn-shadow);
            }
            .confirm-modal .modal-buttons .confirm-no:hover {
                background: var(--input-focus);
                transform: translateY(-1px);
            }

            .message-modal {
                display: none; position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: var(--modal-overlay-strong);
                backdrop-filter: blur(16px) saturate(180%);
                -webkit-backdrop-filter: blur(16px) saturate(180%);
                z-index: 2000;
                justify-content: center; align-items: center;
                padding: 20px;
            }
            .message-modal.active { display: flex; }
            .message-modal .modal-message {
                background: var(--modal-bg);
                backdrop-filter: blur(40px) saturate(180%);
                -webkit-backdrop-filter: blur(40px) saturate(180%);
                border-radius: 22px;
                border: 1px solid var(--panel-border);
                max-width: 800px; width: 100%;
                max-height: 90vh; max-height: 90dvh;
                overflow-y: auto; padding: 32px;
                position: relative; animation: modalIn 0.35s cubic-bezier(0.4, 0, 0.2, 1);
                box-shadow:
                    0 24px 80px var(--panel-shadow),
                    inset 0 1px 0 var(--panel-inset);
            }
            @keyframes modalIn {
                from { opacity: 0; transform: translateY(30px) scale(0.97); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }
            .message-modal .modal-message .close-btn {
                position: absolute; top: 18px; right: 18px;
                background: var(--btn-bg);
                border: 1px solid var(--btn-border);
                color: var(--text-primary);
                width: 40px; height: 40px; border-radius: 50%;
                cursor: pointer; font-size: 20px;
                display: flex; align-items: center; justify-content: center;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                z-index: 10;
                box-shadow: 0 4px 14px var(--btn-shadow);
            }
            .message-modal .modal-message .close-btn:hover {
                background: linear-gradient(135deg, #ef4444, #f87171);
                color: white;
                transform: rotate(90deg);
                box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4);
            }
            .message-modal .modal-message .status-badge {
                position: absolute; top: 24px; right: 68px;
                padding: 4px 12px; border-radius: 20px;
                font-size: 10px; font-weight: 700;
                text-transform: uppercase; letter-spacing: 0.6px; z-index: 10;
                box-shadow: 0 4px 12px rgba(31, 41, 55, 0.15);
            }
            .message-modal .modal-message .status-badge.history {
                background: linear-gradient(135deg, #a78bfa, #8b5cf6);
                color: white;
            }
            .message-modal .modal-message .status-badge.new {
                background: linear-gradient(135deg, #34d399, #14b8a6);
                color: white; animation: pulse 2s infinite;
            }
            .message-modal .modal-message .message-header {
                display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 22px; font-size: 14px;
                flex-wrap: wrap; gap: 10px; padding-right: 110px;
            }
            .message-modal .modal-message .message-chat {
                color: var(--chat-color); font-weight: 700; font-size: 16px;
            }
            .message-modal .modal-message .message-source { color: var(--source-color); font-weight: 700; }
            .message-modal .modal-message .message-date { color: var(--text-secondary); }
            .message-modal .modal-message .message-text {
                font-size: 18px; line-height: 1.8; margin-bottom: 20px;
                word-wrap: break-word; overflow-wrap: break-word;
                white-space: pre-wrap;
                color: var(--text-primary);
            }
            .message-modal .modal-message .message-media img,
            .message-modal .modal-message .message-media video {
                max-width: 100%; max-height: 500px;
                border-radius: 16px;
                border: 1px solid var(--card-border);
                height: auto;
                box-shadow: 0 12px 40px var(--card-shadow);
            }
            .message-modal .modal-message .message-media video { max-height: 600px; }
            .message-modal .modal-message .message-tags {
                display: flex; gap: 8px; flex-wrap: wrap;
                margin-top: 22px; padding-top: 22px;
                border-top: 1px solid var(--border-subtle);
            }

            @media (max-width: 900px) {
                body { padding: 16px; }
                .container { max-width: 100%; }
                .header h1 { font-size: 22px; }
                .slider-container { padding: 24px; }
            }
            @media (max-width: 600px) {
                body { padding: 12px; }
                .header {
                    flex-direction: column; align-items: stretch;
                    padding: 18px 20px; margin-bottom: 18px;
                }
                .header h1 { font-size: 20px; }
                .header h1 small { display: none; }
                .header-controls {
                    flex-direction: row; align-items: center;
                    justify-content: space-between; width: 100%;
                }
                .view-toggle { flex: 1; }
                .view-toggle button { flex: 1; justify-content: center; }
                .filters { grid-template-columns: 1fr; padding: 14px; gap: 8px; }
                .filters .filter-btn { width: 100%; justify-content: center; }
                .slider-container { padding: 18px; border-radius: 18px; }
                .slider-progress { font-size: 13px; margin-bottom: 16px; }
                .slider-message { padding: 20px; border-radius: 14px; }
                .slider-message .message-text { font-size: 16px; line-height: 1.6; }
                .slider-message .message-media img,
                .slider-message .message-media video { max-height: 240px; }
                .message-header { font-size: 12px; }
                .message-date { font-size: 11px; }
                .tag { font-size: 11px; padding: 4px 10px; }
                .slider-controls { flex-direction: row; gap: 10px; margin-top: 16px; }
                .slider-controls .nav-btn {
                    flex: 1; min-width: unset; padding: 12px 16px; font-size: 15px;
                }
                .list-message { padding: 18px; }
                .list-message .message-text { font-size: 14px; }
                .list-message .message-media img,
                .list-message .message-media video {
                    max-width: 150px; max-height: 120px;
                }
                .message-modal { padding: 0; align-items: flex-end; }
                .message-modal .modal-message {
                    border-radius: 24px 24px 0 0;
                    max-height: 92dvh;
                    padding: 26px 20px; border-bottom: none;
                }
                .message-modal .modal-message .close-btn {
                    width: 36px; height: 36px; font-size: 18px;
                }
                .message-modal .modal-message .status-badge {
                    top: 18px; right: 60px; font-size: 9px;
                }
                .message-modal .modal-message .message-header {
                    padding-right: 100px; font-size: 13px;
                }
                .message-modal .modal-message .message-text {
                    font-size: 16px; line-height: 1.7;
                }
                .message-modal .modal-message .message-media img,
                .message-modal .modal-message .message-media video { max-height: 300px; }
                .confirm-modal .modal-content { padding: 26px 22px; }
                .confirm-modal .modal-buttons { flex-direction: column; }
                .confirm-modal .modal-buttons button { width: 100%; }
            }
            @media (max-width: 380px) {
                body { padding: 8px; }
                .header h1 { font-size: 18px; }
                .view-toggle button { padding: 6px 10px; font-size: 12px; }
                .slider-message { padding: 16px; }
                .slider-message .message-text { font-size: 15px; }
                .slider-controls .nav-btn { padding: 10px 8px; font-size: 14px; }
                .message-modal .modal-message { padding: 20px 16px; }
            }
            @media (max-height: 500px) and (orientation: landscape) {
                .message-modal { padding: 0; }
                .message-modal .modal-message {
                    max-height: 100dvh; border-radius: 0; padding: 16px;
                }
                .slider-container { padding: 16px; }
                .slider-message { min-height: auto; }
            }
            @media (min-width: 1400px) {
                .container { max-width: 1100px; }
                .slider-message .message-text { font-size: 19px; }
            }
            ::-webkit-scrollbar { width: 10px; height: 10px; }
            ::-webkit-scrollbar-track { background: transparent; }
            ::-webkit-scrollbar-thumb {
                background: linear-gradient(135deg, var(--scroll-thumb-1), var(--scroll-thumb-2));
                border-radius: 10px;
                border: 2px solid transparent;
                background-clip: padding-box;
            }
            .slider-message, .list-message, .view-toggle button, .filter-btn, .nav-btn {
                -webkit-user-select: none; user-select: none;
            }
        </style>
    </head>
    <body>
        <div class="container" id="app">
            <div class="header">
                <h1>➤ TMGbyToniK <small>сообщения из групп/каналов</small></h1>
                <div class="header-controls">
                    <div class="view-toggle">
                        <button id="viewSlider" class="active" onclick="setView('slider')">🎠 <span>Слайдер</span></button>
                        <button id="viewList" onclick="setView('list')">📋 <span>Список</span></button>
                    </div>
                    <button class="theme-toggle" id="themeToggle" onclick="toggleTheme()" title="Переключить тему" aria-label="Переключить тему">
                        <svg class="icon-sun" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="5"></circle>
                            <line x1="12" y1="1" x2="12" y2="3"></line>
                            <line x1="12" y1="21" x2="12" y2="23"></line>
                            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                            <line x1="1" y1="12" x2="3" y2="12"></line>
                            <line x1="21" y1="12" x2="23" y2="12"></line>
                            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                        </svg>
                        <svg class="icon-moon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                        </svg>
                    </button>
                </div>
            </div>

            <div class="filters">
                <input type="text" id="searchInput" placeholder="🔍 Поиск..." oninput="applyFilters()" />
                <select id="sortOrder" onchange="applyFilters()">
                    <option value="newest">📅 Сначала новые</option>
                    <option value="oldest">📅 Сначала старые</option>
                </select>
                <select id="filterGroup" onchange="applyFilters()">
                    <option value="all">💬 Все группы</option>
                </select>
                <select id="filterMedia" onchange="applyFilters()">
                    <option value="all">📋 Все</option>
                    <option value="with_media">📷 С медиа</option>
                    <option value="without_media">📝 Без медиа</option>
                    <option value="photo">🖼️ Только фото</option>
                    <option value="video">🎥 Только видео</option>
                </select>
                <select id="filterStatus" onchange="applyFilters()">
                    <option value="all">📋 Все статусы</option>
                    <option value="history">📜 Из истории</option>
                    <option value="new">✅ Новые</option>
                </select>
                <select id="filterKev" onchange="applyFilters()">
                    <option value="all">🤖 Все Kev</option>
                    <option value="important">🔥 Важные</option>
                    <option value="urgent">⚡ Срочные</option>
                </select>
                <button class="filter-btn warning" onclick="loadAllGroupMessages()">📥 Все из группы</button>
                <button class="filter-btn danger" onclick="showClearMediaConfirm()">🗑️ Медиа</button>
                <button class="filter-btn danger" onclick="showClearConfirm()">🗑️ Лента</button>
                <button class="filter-btn success" onclick="loadMessages()">🔄 Обновить</button>
            </div>

            <div class="slider-container" id="sliderView">
                <div class="slider-progress">
                    <span id="sliderProgressText">Сообщение <strong id="currentNum">1</strong> из <strong id="totalNum">0</strong></span>
                </div>
                <div class="slider-card" id="sliderCard"></div>
                <div class="slider-controls">
                    <button class="nav-btn" id="prevBtn" onclick="prevMessage()">◀ Назад</button>
                    <button class="nav-btn" id="nextBtn" onclick="nextMessage()">Вперед ▶</button>
                </div>
            </div>

            <div class="list-view" id="listView">
                <div id="listContainer"></div>
                <div id="loadMoreContainer"></div>
            </div>
        </div>

        <div class="confirm-modal" id="confirmModal">
            <div class="modal-content">
                <h3>⚠️ Подтверждение</h3>
                <p>Вы уверены, что хотите очистить всю ленту сообщений? Это действие нельзя отменить!</p>
                <div class="modal-buttons">
                    <button class="confirm-yes" onclick="clearMessages()">Да, очистить</button>
                    <button class="confirm-no" onclick="closeConfirm()">Отмена</button>
                </div>
            </div>
        </div>

        <div class="message-modal" id="messageModal">
            <div class="modal-message" id="modalMessageContent"></div>
        </div>

        <script>
            let allMessages = [];
            let filteredMessages = [];
            let currentIndex = 0;
            let currentView = 'slider';
            let currentPage = 1;
            let totalPages = 1;
            let isLoading = false;
            let hasMore = true;
            let selectedGroup = 'all';
            let kevCategories = {};

            function toggleTheme() {
                const current = document.documentElement.getAttribute('data-theme') || 'light';
                const next = current === 'light' ? 'dark' : 'light';
                document.documentElement.setAttribute('data-theme', next);
                try { localStorage.setItem('theme', next); } catch (e) {}
                const meta = document.querySelector('meta[name="theme-color"]');
                if (meta) meta.setAttribute('content', next === 'dark' ? '#070b14' : '#eef2f9');
            }

            function formatDate(timestamp) {
                if (!timestamp) return 'Нет даты';
                try {
                    const date = new Date(timestamp.replace(' ', 'T'));
                    if (isNaN(date.getTime())) return timestamp;
                    const now = new Date();
                    const diff = now - date;
                    if (diff < 86400000 && date.getDate() === now.getDate()) {
                        return `Сегодня в ${date.toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'})}`;
                    }
                    if (diff < 172800000) {
                        return `Вчера в ${date.toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'})}`;
                    }
                    return date.toLocaleString('ru-RU', {
                        day: '2-digit', month: '2-digit', year: 'numeric',
                        hour: '2-digit', minute: '2-digit'
                    });
                } catch (e) { return timestamp; }
            }

            function escapeHtml(text) {
                if (!text) return '';
                const div = document.createElement('div');
                div.textContent = text;
                let escaped = div.innerHTML;
                escaped = escaped.replace(/(https?:\\/\\/[^\\s<>"']+)/g,
                    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
                escaped = escaped.replace(/(^|[^>])@([a-zA-Z0-9_]+)/g,
                    '$1<a href="https://t.me/$2" target="_blank" rel="noopener noreferrer">@$2</a>');
                escaped = escaped.replace(/(^|[^>])#([a-zA-Z0-9_]+)/g,
                    '$1<a href="https://t.me/hashtag/$2" target="_blank" rel="noopener noreferrer">#$2</a>');
                return escaped;
            }

            function renderMessageText(msg) {
                if (msg.message_html && msg.message_html !== msg.message) {
                    return msg.message_html;
                }
                return escapeHtml(msg.message);
            }

            function getMediaType(media) {
                if (!media || media.length === 0) return null;
                const types = media.map(m => m.type);
                if (types.includes('photo') && types.includes('video')) return 'mixed';
                if (types.includes('photo')) return 'photo';
                if (types.includes('video')) return 'video';
                return 'document';
            }

            function renderMedia(media) {
                if (!media || media.length === 0) return '';
                let html = '<div class="message-media">';
                media.forEach(item => {
                    const source = item.url ? escapeHtml(item.url) : `data:${escapeHtml(item.mime_type)};base64,${item.data || ''}`;
                    if (item.type === 'photo') {
                        html += `<img src="${source}" alt="Фото" loading="lazy" />`;
                    } else if (item.type === 'video') {
                        html += `<video controls preload="metadata"><source src="${source}" type="${escapeHtml(item.mime_type || 'video/mp4')}">Ваш браузер не поддерживает видео</video>`;
                    }
                });
                html += '</div>';
                return html;
            }

            function getMediaTag(msg) {
                const mediaType = getMediaType(msg.media);

                if (msg.has_media && (!msg.media || msg.media.length === 0)) {
                    return '<span class="tag tag-not-downloaded">⚠️ Медиа не скачано</span>';
                }

                if (!mediaType) return '';
                if (mediaType === 'photo') return '<span class="tag tag-photo">🖼️ Фото</span>';
                if (mediaType === 'video') return '<span class="tag tag-video">🎥 Видео</span>';
                if (mediaType === 'mixed') return '<span class="tag tag-media">📷 Фото + Видео</span>';
                return '<span class="tag tag-media">📎 Документ</span>';
            }

            function renderMediaPlaceholder(msg) {
                if (msg.has_media && (!msg.media || msg.media.length === 0)) {
                    return '';
                }
                return renderMedia(msg.media);
            }

            function renderKevTags(msg) {
                if (msg.kev_error || msg.kev_important === null || msg.kev_important === undefined) {
                    return '';
                }
                let tags = '';
                const cat = msg.kev_category || 'other';
                const imp = msg.kev_important;
                const urg = msg.kev_urgency;

                const catLabel = kevCategories[cat] || cat;
                tags += `<span class="tag tag-kev-cat">${catLabel}</span>`;

                if (imp >= 0.7) {
                    tags += `<span class="tag tag-kev-important">🔥 Важное (${(imp * 100).toFixed(0)}%)</span>`;
                } else if (imp <= 0.3) {
                    tags += `<span class="tag tag-kev-skip">🗑️ Неважное (${(imp * 100).toFixed(0)}%)</span>`;
                }

                if (urg !== null && urg !== undefined) {
                    if (urg >= 0.7) {
                        tags += `<span class="tag tag-kev-urgent">⚡ Срочно</span>`;
                    } else if (urg <= 0.3) {
                        tags += `<span class="tag tag-kev-later">⏳ Потом</span>`;
                    }
                }

                return tags;
            }

            function loadKevCategories() {
                fetchJson('/api/kev_categories')
                    .then(data => {
                        if (data.status === 'success') {
                            kevCategories = data.categories;
                            updateKevFilterOptions();
                        }
                    })
                    .catch(error => console.error('Ошибка при загрузке категорий Kev:', error));
            }

            function updateKevFilterOptions() {
                const filter = document.getElementById('filterKev');
                if (!filter) return;
                let html = '<option value="all">🤖 Все Kev</option>';
                html += '<option value="important">🔥 Важные</option>';
                html += '<option value="urgent">⚡ Срочные</option>';
                for (const [key, label] of Object.entries(kevCategories)) {
                    html += `<option value="cat:${key}">${label}</option>`;
                }
                filter.innerHTML = html;
            }

            function updateGroupsList() {
                fetchJson('/api/groups')
                    .then(data => {
                        if (data.status === 'success') {
                            const groupFilter = document.getElementById('filterGroup');
                            let options = '<option value="all">💬 Все группы</option>';

                            data.groups.forEach(group => {
                                const msgCount = group.message_count > 0 ? ` (${group.message_count})` : '';
                                options += `<option value="${group.chat_id}">💬 ${escapeHtml(group.title)}${msgCount}</option>`;
                            });

                            groupFilter.innerHTML = options;
                            groupFilter.value = selectedGroup;
                        }
                    })
                    .catch(error => console.error('Ошибка при загрузке групп:', error));
            }

            function openMessageModal(msg) {
                const modal = document.getElementById('messageModal');
                const modalContent = document.getElementById('modalMessageContent');
                const source = msg.sender_username ? `@${msg.sender_username}` : (msg.sender_first_name || `User ${msg.sender_id}`);
                const chatTitle = msg.chat_title || 'Группа';
                const date = formatDate(msg.timestamp);
                const text = renderMessageText(msg);
                const mediaHtml = renderMediaPlaceholder(msg);
                const hasMedia = msg.media && msg.media.length > 0;
                const hasText = msg.message && msg.message.length > 0;
                const mediaTag = getMediaTag(msg);
                const isHistory = msg.from_history || false;
                const statusBadge = isHistory ? '<span class="status-badge history">📜 История</span>' : '<span class="status-badge new">✅ Новое</span>';
                const statusTag = isHistory ? '<span class="tag tag-history">📜 Из истории</span>' : '<span class="tag tag-processed">✅ Новое</span>';

                modalContent.innerHTML = `
                    <button class="close-btn" onclick="closeMessageModal()">✕</button>
                    ${statusBadge}
                    <div class="message-header">
                        <span>
                            <span class="message-chat">💬 ${escapeHtml(chatTitle)}</span>
                            <span class="message-source"> | ${escapeHtml(source)}</span>
                        </span>
                        <span class="message-date">${date}</span>
                    </div>
                    <div class="message-text">${text}</div>
                    ${mediaHtml}
                    <div class="message-tags">
                        <span class="tag tag-group">💬 Группа</span>
                        ${statusTag}
                        ${mediaTag}
                        ${hasMedia && !hasText ? `<span class="tag tag-no-text">🖼️ Только медиа</span>` : ''}
                        ${renderKevTags(msg)}
                    </div>
                `;
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }

            function closeMessageModal() {
                document.getElementById('messageModal').classList.remove('active');
                document.body.style.overflow = '';
            }

            async function fetchJson(url, options) {
                const response = await fetch(url, options);
                const rawBody = await response.text();
                let data;
                try { data = rawBody ? JSON.parse(rawBody) : {}; }
                catch (error) { throw new Error(`Сервер вернул некорректный ответ (HTTP ${response.status})`); }
                if (!response.ok) { throw new Error(data.message || `Ошибка сервера (HTTP ${response.status})`); }
                return data;
            }

            function loadStats() {
                fetchJson('/api/stats')
                    .then(data => {
                        const histEl = document.getElementById('historyCount');
                        const procEl = document.getElementById('processedCount');
                        if (histEl) histEl.textContent = data.from_history || 0;
                        if (procEl) procEl.textContent = data.processed || 0;
                    })
                    .catch(error => console.error('Ошибка при загрузке статистики:', error));
            }

            function loadMessages(page = 1) {
                if (isLoading) return;
                isLoading = true;
                return fetchJson(`/api/messages?page=${page}&per_page=20`)
                    .then(data => {
                        if (page === 1) {
                            allMessages = data.messages;
                        } else {
                            const existingIds = new Set(allMessages.map(m => m.message_id));
                            const newMessages = data.messages.filter(m => !existingIds.has(m.message_id));
                            allMessages = allMessages.concat(newMessages);
                        }
                        totalPages = data.total_pages;
                        currentPage = page;
                        hasMore = page < totalPages;
                        applyFilters();
                        updateStats();
                        loadStats();
                        isLoading = false;
                    })
                    .catch(error => {
                        console.error('Ошибка при загрузке сообщений:', error);
                        document.getElementById('sliderCard').innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>Ошибка при загрузке сообщений</p></div>';
                        isLoading = false;
                    });
            }

            function loadAllGroupMessages() {
                const groupFilter = document.getElementById('filterGroup').value;

                if (groupFilter === 'all') {
                    alert('⚠️ Выберите конкретную группу');
                    return;
                }

                const groupName = document.getElementById('filterGroup').selectedOptions[0].text;

                fetchJson(`/api/messages_by_group?chat_id=${groupFilter}`)
                    .then(data => {
                        if (data.status === 'success') {
                            allMessages = data.messages;
                            totalPages = 1;
                            currentPage = 1;
                            hasMore = false;
                            selectedGroup = groupFilter;

                            applyFilters();
                            updateStats();
                            loadStats();

                            alert(`✅ Загружено ${data.total} сообщений из группы "${groupName}"`);
                        } else {
                            alert('❌ Ошибка: ' + data.message);
                        }
                    })
                    .catch(error => {
                        console.error('Ошибка при загрузке сообщений группы:', error);
                        alert('❌ Ошибка при загрузке сообщений группы');
                    });
            }

            function applyFilters() {
                const searchQuery = document.getElementById('searchInput').value.toLowerCase().trim();
                const sortOrder = document.getElementById('sortOrder').value;
                const mediaFilter = document.getElementById('filterMedia').value;
                const statusFilter = document.getElementById('filterStatus').value;
                const groupFilter = document.getElementById('filterGroup').value;
                const kevFilter = document.getElementById('filterKev').value;
                selectedGroup = groupFilter;

                let filtered = allMessages.filter(msg => {
                    const text = (msg.message || '').toLowerCase();
                    if (searchQuery && !text.includes(searchQuery)) return false;
                    const hasMedia = msg.media && msg.media.length > 0;
                    const mediaType = getMediaType(msg.media);
                    if (mediaFilter === 'with_media' && !hasMedia) return false;
                    if (mediaFilter === 'without_media' && hasMedia) return false;
                    if (mediaFilter === 'photo' && mediaType !== 'photo') return false;
                    if (mediaFilter === 'video' && mediaType !== 'video') return false;
                    if (statusFilter === 'history' && !msg.from_history) return false;
                    if (statusFilter === 'new' && msg.from_history) return false;
                    if (groupFilter !== 'all' && msg.chat_id != groupFilter) return false;

                    if (kevFilter === 'important') {
                        if (msg.kev_important === null || msg.kev_important === undefined || msg.kev_important < 0.7) return false;
                    }
                    if (kevFilter === 'urgent') {
                        if (msg.kev_urgency === null || msg.kev_urgency === undefined || msg.kev_urgency < 0.7) return false;
                    }
                    if (kevFilter.startsWith('cat:')) {
                        const wanted = kevFilter.slice(4);
                        if (msg.kev_category !== wanted) return false;
                    }

                    return true;
                });

                if (sortOrder === 'newest') {
                    filtered.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                } else {
                    filtered.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
                }

                filteredMessages = filtered;
                if (currentIndex >= filteredMessages.length) { currentIndex = Math.max(0, filteredMessages.length - 1); }
                if (filteredMessages.length === 0) currentIndex = 0;
                renderCurrentView();
                updateControls();
                updateStats();
            }

            function renderCurrentView() {
                if (currentView === 'slider') { renderSlider(); } else { renderList(); }
            }

            function renderSlider() {
                const sliderCard = document.getElementById('sliderCard');
                if (filteredMessages.length === 0) {
                    sliderCard.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>Нет сообщений из групп</p></div>';
                    document.getElementById('currentNum').textContent = '0';
                    document.getElementById('totalNum').textContent = '0';
                    document.getElementById('prevBtn').disabled = true;
                    document.getElementById('nextBtn').disabled = true;
                    return;
                }
            
                const msg = filteredMessages[currentIndex];
                const source = msg.sender_username ? `@${msg.sender_username}` : (msg.sender_first_name || `User ${msg.sender_id}`);
                const chatTitle = msg.chat_title || 'Группа';
                const date = formatDate(msg.timestamp);
                const text = renderMessageText(msg);
                const mediaHtml = renderMediaPlaceholder(msg);
                const hasMedia = msg.media && msg.media.length > 0;
                const hasText = msg.message && msg.message.length > 0;
                const mediaTag = getMediaTag(msg);
                const isHistory = msg.from_history || false;
                const statusBadge = isHistory ? '<span class="status-badge history">📜 История</span>' : '<span class="status-badge new">✅ Новое</span>';
                const statusTag = isHistory ? '<span class="tag tag-history">📜 Из истории</span>' : '<span class="tag tag-processed">✅ Новое</span>';
            
                sliderCard.innerHTML = `
                    <div class="slider-message" onclick="openMessageModal(filteredMessages[${currentIndex}])">
                        ${statusBadge}
                        <div class="message-header">
                            <span>
                                <span class="message-chat">💬 ${escapeHtml(chatTitle)}</span>
                                <span class="message-source"> | ${escapeHtml(source)}</span>
                            </span>
                            <span class="message-date">${date}</span>
                        </div>
                        <div class="message-text">${text}</div>
                        ${mediaHtml}
                        <div class="message-tags">
                            <span class="tag tag-group">💬 Группа</span>
                            ${statusTag}
                            ${mediaTag}
                            ${hasMedia && !hasText ? `<span class="tag tag-no-text">🖼️ Только медиа</span>` : ''}
                            ${renderKevTags(msg)}
                        </div>
                    </div>
                `;
            
                document.getElementById('currentNum').textContent = currentIndex + 1;
                document.getElementById('totalNum').textContent = filteredMessages.length;
                document.getElementById('prevBtn').disabled = currentIndex === 0;
                document.getElementById('nextBtn').disabled = currentIndex === filteredMessages.length - 1;
                
                if (filteredMessages.length - currentIndex <= 5 && hasMore && !isLoading) {
                    loadMessages(currentPage + 1).then(() => {
                        renderSlider();
                        updateControls();
                    });
                }
            }

            function renderList() {
                const listContainer = document.getElementById('listContainer');
                if (filteredMessages.length === 0) {
                    listContainer.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>Нет сообщений из групп</p></div>';
                    return;
                }

                let html = '';
                filteredMessages.forEach((msg, index) => {
                    const source = msg.sender_username ? `@${msg.sender_username}` : (msg.sender_first_name || `User ${msg.sender_id}`);
                    const chatTitle = msg.chat_title || 'Группа';
                    const date = formatDate(msg.timestamp);
                    const text = renderMessageText(msg);
                    const mediaHtml = renderMediaPlaceholder(msg);
                    const hasMedia = msg.media && msg.media.length > 0;
                    const hasText = msg.message && msg.message.length > 0;
                    const mediaTag = getMediaTag(msg);
                    const isHistory = msg.from_history || false;
                    const statusBadge = isHistory ? '<span class="status-badge history">📜 История</span>' : '<span class="status-badge new">✅ Новое</span>';
                    const statusTag = isHistory ? '<span class="tag tag-history">📜 Из истории</span>' : '<span class="tag tag-processed">✅ Новое</span>';

                    html += `
                        <div class="list-message" onclick="openMessageModal(filteredMessages[${index}])">
                            ${statusBadge}
                            <div class="message-header">
                                <span>
                                    <span class="message-chat">💬 ${escapeHtml(chatTitle)}</span>
                                    <span class="message-source"> | ${escapeHtml(source)}</span>
                                </span>
                                <span class="message-date">${date}</span>
                            </div>
                            <div class="message-text">${text}</div>
                            ${mediaHtml}
                            <div class="message-tags">
                                <span class="tag tag-group">💬 Группа</span>
                                ${statusTag}
                                ${mediaTag}
                                ${hasMedia && !hasText ? `<span class="tag tag-no-text">🖼️ Только медиа</span>` : ''}
                                ${renderKevTags(msg)}
                            </div>
                        </div>
                    `;
                });

                listContainer.innerHTML = html;
            }

            function nextMessage() {
                if (currentIndex < filteredMessages.length - 1) {
                    currentIndex++;
                    renderSlider();
                    updateControls();
                    
                    if (filteredMessages.length - currentIndex <= 5 && hasMore && !isLoading) {
                        loadMessages(currentPage + 1).then(() => {
                            renderSlider();
                            updateControls();
                        });
                    }
                } else if (hasMore && !isLoading) {
                    loadMessages(currentPage + 1).then(() => {
                        if (currentIndex < filteredMessages.length - 1) {
                            currentIndex++;
                            renderSlider();
                            updateControls();
                        }
                    });
                }
            }

            function prevMessage() {
                if (currentIndex > 0) {
                    currentIndex--;
                    renderSlider();
                    updateControls();
                }
            }

            function updateControls() {
                if (currentView === 'slider') {
                    const prevBtn = document.getElementById('prevBtn');
                    const nextBtn = document.getElementById('nextBtn');
                    if (prevBtn && nextBtn) {
                        prevBtn.disabled = currentIndex === 0 || filteredMessages.length === 0;
                        nextBtn.disabled = (currentIndex === filteredMessages.length - 1 && !hasMore) || filteredMessages.length === 0;
                    }
                }
            }

            function updateStats() {
                const totalEl = document.getElementById('totalCount');
                const mediaEl = document.getElementById('mediaCount');
                const sliderCounter = document.getElementById('sliderCounter');
                const currentIdx = document.getElementById('currentIndex');
                const totalFiltered = document.getElementById('totalFiltered');

                if (totalEl) totalEl.textContent = allMessages.length;
                if (mediaEl) {
                    const mediaItems = allMessages.filter(msg => msg.media && msg.media.length > 0).length;
                    mediaEl.textContent = mediaItems;
                }
                if (sliderCounter && currentIdx && totalFiltered) {
                    if (currentView === 'slider') {
                        sliderCounter.style.display = 'inline';
                        currentIdx.textContent = filteredMessages.length > 0 ? currentIndex + 1 : 0;
                        totalFiltered.textContent = filteredMessages.length;
                    } else {
                        sliderCounter.style.display = 'none';
                    }
                }
            }

            function setView(view) {
                currentView = view;
                document.getElementById('viewSlider').classList.toggle('active', view === 'slider');
                document.getElementById('viewList').classList.toggle('active', view === 'list');
                document.getElementById('sliderView').style.display = view === 'slider' ? 'block' : 'none';
                document.getElementById('listView').classList.toggle('active', view === 'list');
                renderCurrentView();
                updateStats();
            }

            function showClearConfirm() {
                document.getElementById('confirmModal').classList.add('active');
            }

            function closeConfirm() {
                document.getElementById('confirmModal').classList.remove('active');
            }

            function clearMessages() {
                fetchJson('/api/clear', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
                .then(data => {
                    if (data.status === 'success') {
                        allMessages = [];
                        filteredMessages = [];
                        currentIndex = 0;
                        currentPage = 1;
                        hasMore = false;
                        selectedGroup = 'all';
                        renderCurrentView();
                        updateStats();
                        updateControls();
                        loadStats();
                        closeConfirm();
                        alert('✅ Лента очищена!');
                    } else {
                        alert('❌ Ошибка: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Ошибка при очистке:', error);
                    alert('❌ Ошибка при очистке ленты');
                });
            }

            function showClearMediaConfirm() {
                if (confirm('🗑️ Вы уверены, что хотите очистить всю папку с медиа? Это действие нельзя отменить!')) {
                    clearMedia();
                }
            }

            function clearMedia() {
                fetchJson('/api/clear_media', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                })
                .then(data => {
                    if (data.status === 'success') {
                        alert('✅ Медиа очищена!');
                        loadMessages(1);
                    } else {
                        alert('❌ Ошибка: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Ошибка при очистке медиа:', error);
                    alert('❌ Ошибка при очистке медиа');
                });
            }

            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    closeConfirm();
                    closeMessageModal();
                }
                if (currentView === 'slider') {
                    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                        e.preventDefault();
                        nextMessage();
                    }
                    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                        e.preventDefault();
                        prevMessage();
                    }
                    if (e.key === ' ' || e.code === 'Space') {
                        e.preventDefault();
                        nextMessage();
                    }
                }
            });

            document.getElementById('messageModal').addEventListener('click', function(e) {
                if (e.target === this) { closeMessageModal(); }
            });

            let scrollTimeout;
            document.addEventListener('scroll', function() {
                if (currentView === 'list') {
                    clearTimeout(scrollTimeout);
                    scrollTimeout = setTimeout(() => {
                        const scrollPosition = window.innerHeight + window.scrollY;
                        const bottom = document.documentElement.scrollHeight - 200;
                        if (scrollPosition >= bottom && hasMore && !isLoading) { 
                            loadMessages(currentPage + 1);
                        }
                    }, 200);
                }
            });

            document.addEventListener('DOMContentLoaded', () => {
                loadKevCategories();
                updateGroupsList();
                loadMessages(1);
                setView('slider');
                loadStats();
            });
        </script>
    </body>
    </html>
    """

    return render_template_string(site_text)


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT)