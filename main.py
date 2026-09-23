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
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <meta name="theme-color" content="#0a0e1a">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <title>Telegram Groups Feed</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
            html { font-size: 16px; -webkit-text-size-adjust: 100%; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                background: #0a0e1a; color: #e4e9f2;
                padding: 20px;
                min-height: 100vh;
                min-height: 100dvh;
                display: flex;
                justify-content: center;
                align-items: flex-start;
                overflow-x: hidden;
            }
            .container { max-width: 900px; width: 100%; margin: 0 auto; }
            .header {
                display: flex; justify-content: space-between; align-items: center;
                padding: 20px 0; border-bottom: 1px solid #1e2a3a;
                margin-bottom: 30px; flex-wrap: wrap; gap: 10px;
            }
            .header h1 {
                font-size: 24px; font-weight: 600;
                background: linear-gradient(135deg, #6c5ce7, #00b894);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .header h1 small {
                font-size: 14px; -webkit-text-fill-color: #6a7a8e; background: none;
            }
            .header-controls { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
            .view-toggle {
                display: flex; gap: 6px; background: #141f2d; padding: 4px;
                border-radius: 10px; border: 1px solid #1e2a3a;
            }
            .view-toggle button {
                background: none; border: none; color: #6a7a8e;
                padding: 8px 16px; border-radius: 8px; cursor: pointer;
                font-size: 13px; transition: all 0.3s;
                min-height: 40px; display: flex; align-items: center;
                gap: 4px; white-space: nowrap;
            }
            .view-toggle button.active { background: #6c5ce7; color: white; }
            .view-toggle button:hover:not(.active) { background: #1e2a3a; color: #e4e9f2; }
            .filters {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 10px; margin-bottom: 20px;
                background: #141f2d; padding: 15px;
                border-radius: 12px; border: 1px solid #1e2a3a;
            }
            .filters input, .filters select {
                padding: 12px 16px; background: #0a0e1a;
                border: 1px solid #1e2a3a; border-radius: 8px;
                color: #e4e9f2; font-size: 14px; width: 100%;
                min-height: 44px;
                -webkit-appearance: none; appearance: none;
            }
            .filters select {
                background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236a7a8e' stroke-width='2'%3e%3cpolyline points='6 9 12 15 18 9'/%3e%3c/svg%3e");
                background-repeat: no-repeat;
                background-position: right 10px center;
                background-size: 16px;
                padding-right: 36px;
            }
            .filters input::placeholder { color: #6a7a8e; }
            .filters select option { background: #0a0e1a; }
            .filters .filter-btn {
                padding: 12px 20px; background: #6c5ce7;
                border: none; border-radius: 8px; color: white;
                cursor: pointer; font-size: 14px;
                transition: all 0.3s; min-height: 44px;
                display: flex; align-items: center;
                justify-content: center; gap: 6px; white-space: nowrap;
            }
            .filters .filter-btn:hover { background: #5a4bd1; }
            .filters .filter-btn:active { transform: scale(0.97); }
            .filters .filter-btn.danger { background: #e74c3c; }
            .filters .filter-btn.danger:hover { background: #c0392b; }
            .filters .filter-btn.success { background: #00b894; }
            .filters .filter-btn.success:hover { background: #00a381; }
            .filters .filter-btn.warning { background: #f39c12; }
            .filters .filter-btn.warning:hover { background: #e67e22; }
            .slider-container {
                position: relative; background: #141f2d;
                border-radius: 16px; border: 1px solid #1e2a3a;
                padding: 30px; min-height: 300px;
                display: flex; flex-direction: column; justify-content: center;
            }
            .slider-progress {
                text-align: center; color: #6a7a8e;
                font-size: 14px; margin-bottom: 20px;
            }
            .slider-progress strong { color: #e4e9f2; }
            .slider-card { flex: 1; }
            .slider-message {
                background: #0a0e1a; border-radius: 12px; padding: 24px;
                border: 1px solid #1e2a3a; min-height: 200px;
                display: flex; flex-direction: column; position: relative;
                cursor: pointer; transition: all 0.3s;
            }
            .slider-message:hover {
                border-color: #6c5ce7;
                box-shadow: 0 8px 25px rgba(108, 92, 231, 0.1);
            }
            .slider-message .status-badge {
                position: absolute; top: -10px; right: -10px;
                padding: 3px 12px; border-radius: 20px;
                font-size: 10px; font-weight: 600;
                text-transform: uppercase; letter-spacing: 0.5px;
            }
            .slider-message .status-badge.history { background: #6c5ce7; color: white; }
            .slider-message .status-badge.new { background: #00b894; color: white; animation: pulse 2s infinite; }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
            .message-header {
                display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 12px; font-size: 13px; flex-wrap: wrap; gap: 5px;
            }
            .message-chat { color: #00b894; font-weight: 600; }
            .message-source { color: #6c5ce7; font-weight: 600; }
            .message-date { color: #6a7a8e; font-size: 12px; }
            .slider-message .message-text {
                font-size: 18px; line-height: 1.7;
                margin-bottom: 16px; flex: 1;
                word-wrap: break-word; overflow-wrap: break-word;
            }
            .slider-message .message-text a,
            .list-message .message-text a,
            .modal-message .message-text a {
                color: #00b894; text-decoration: underline;
                word-break: break-all; transition: color 0.3s;
            }
            .slider-message .message-text a:hover,
            .list-message .message-text a:hover,
            .modal-message .message-text a:hover {
                color: #00d4b8; text-decoration: none;
            }
            .slider-message .message-text a[href*="t.me"],
            .list-message .message-text a[href*="t.me"],
            .modal-message .message-text a[href*="t.me"] {
                color: #6c5ce7;
            }
            .slider-message .message-text a[href*="t.me"]:hover,
            .list-message .message-text a[href*="t.me"]:hover,
            .modal-message .message-text a[href*="t.me"]:hover {
                color: #8b7cf7;
            }
            .message-media {
                display: flex; gap: 10px; flex-wrap: wrap;
                margin: 10px 0; justify-content: center;
            }
            .message-media img, .message-media video {
                max-width: 100%; max-height: 400px;
                border-radius: 8px; border: 1px solid #1e2a3a;
                height: auto;
            }
            .message-media video { max-height: 500px; }
            .message-tags {
                display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px;
            }
            .tag {
                padding: 4px 12px; border-radius: 20px;
                font-size: 12px; font-weight: 500;
                white-space: nowrap;
            }
            .tag-media { background: rgba(0, 206, 201, 0.2); color: #00cec9; border: 1px solid rgba(0, 206, 201, 0.3); }
            .tag-no-text { background: rgba(255, 165, 0, 0.2); color: #ffa500; border: 1px solid rgba(255, 165, 0, 0.3); }
            .tag-photo { background: rgba(108, 92, 231, 0.2); color: #a78bfa; border: 1px solid rgba(108, 92, 231, 0.3); }
            .tag-video { background: rgba(231, 76, 60, 0.2); color: #ff7675; border: 1px solid rgba(231, 76, 60, 0.3); }
            .tag-group { background: rgba(0, 184, 148, 0.2); color: #00b894; border: 1px solid rgba(0, 184, 148, 0.3); }
            .tag-history { background: rgba(108, 92, 231, 0.2); color: #a78bfa; border: 1px solid rgba(108, 92, 231, 0.3); }
            .tag-processed { background: rgba(0, 184, 148, 0.2); color: #00b894; border: 1px solid rgba(0, 184, 148, 0.3); }
            .tag-not-downloaded { background: rgba(231, 76, 60, 0.2); color: #e74c3c; border: 1px solid rgba(231, 76, 60, 0.3); }
            .tag-kev-cat { background: rgba(108, 92, 231, 0.2); color: #a78bfa; border: 1px solid rgba(108, 92, 231, 0.3); }
            .tag-kev-important { background: rgba(231, 76, 60, 0.2); color: #ff7675; border: 1px solid rgba(231, 76, 60, 0.3); }
            .tag-kev-skip { background: rgba(120, 120, 120, 0.2); color: #b0b0b0; border: 1px solid rgba(120, 120, 120, 0.3); }
            .tag-kev-urgent { background: rgba(243, 156, 18, 0.2); color: #f39c12; border: 1px solid rgba(243, 156, 18, 0.3); }
            .tag-kev-later { background: rgba(0, 184, 148, 0.15); color: #00b894; border: 1px solid rgba(0, 184, 148, 0.3); }
            .slider-controls {
                display: flex; justify-content: center; gap: 20px;
                margin-top: 20px; flex-wrap: wrap;
            }
            .slider-controls .nav-btn {
                background: #1e2a3a; border: 1px solid #2a3a4a;
                color: #e4e9f2; padding: 12px 32px;
                border-radius: 10px; cursor: pointer;
                font-size: 16px; transition: all 0.3s;
                min-width: 120px; min-height: 48px;
                display: flex; align-items: center; justify-content: center;
            }
            .slider-controls .nav-btn:hover:not(:disabled) {
                background: #6c5ce7; border-color: #6c5ce7;
            }
            .slider-controls .nav-btn:active:not(:disabled) { transform: scale(0.97); }
            .slider-controls .nav-btn:disabled { opacity: 0.3; cursor: not-allowed; }
            .list-view { display: none; }
            .list-view.active { display: block; }
            .list-message {
                background: #141f2d; border-radius: 12px; padding: 20px;
                margin-bottom: 16px; border: 1px solid #1e2a3a;
                transition: all 0.3s ease; position: relative; cursor: pointer;
            }
            .list-message:hover {
                border-color: #6c5ce7; transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(108, 92, 231, 0.1);
            }
            .list-message .status-badge {
                position: absolute; top: -8px; right: -8px;
                padding: 2px 10px; border-radius: 20px;
                font-size: 9px; font-weight: 600;
                text-transform: uppercase; letter-spacing: 0.5px;
            }
            .list-message .status-badge.history { background: #6c5ce7; color: white; }
            .list-message .status-badge.new { background: #00b894; color: white; animation: pulse 2s infinite; }
            .list-message .message-text {
                font-size: 15px; line-height: 1.6;
                margin-bottom: 12px;
                word-wrap: break-word; overflow-wrap: break-word;
            }
            .list-message .message-media img,
            .list-message .message-media video {
                max-width: 200px; max-height: 150px;
                border-radius: 8px; border: 1px solid #1e2a3a;
                object-fit: cover;
            }
            .empty-state {
                text-align: center; padding: 60px 20px; color: #6a7a8e;
            }
            .empty-state .icon { font-size: 48px; margin-bottom: 20px; }
            .confirm-modal {
                display: none; position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0, 0, 0, 0.8); z-index: 1000;
                justify-content: center; align-items: center;
                padding: 20px;
            }
            .confirm-modal.active { display: flex; }
            .confirm-modal .modal-content {
                background: #141f2d; padding: 30px; border-radius: 16px;
                border: 1px solid #1e2a3a; max-width: 400px;
                width: 100%; text-align: center;
            }
            .confirm-modal .modal-content h3 { margin-bottom: 15px; color: #e74c3c; }
            .confirm-modal .modal-content p { margin-bottom: 20px; color: #8b9bb5; }
            .confirm-modal .modal-buttons { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
            .confirm-modal .modal-buttons button {
                padding: 12px 30px; border: none; border-radius: 8px;
                cursor: pointer; font-size: 14px; transition: all 0.3s;
                min-height: 44px; flex: 1; min-width: 120px;
            }
            .confirm-modal .modal-buttons .confirm-yes { background: #e74c3c; color: white; }
            .confirm-modal .modal-buttons .confirm-yes:hover { background: #c0392b; }
            .confirm-modal .modal-buttons .confirm-no { background: #1e2a3a; color: #e4e9f2; }
            .confirm-modal .modal-buttons .confirm-no:hover { background: #2a3a4a; }
            .message-modal {
                display: none; position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0, 0, 0, 0.9); z-index: 2000;
                justify-content: center; align-items: center;
                padding: 20px;
            }
            .message-modal.active { display: flex; }
            .message-modal .modal-message {
                background: #141f2d; border-radius: 16px;
                border: 1px solid #2a3a4a;
                max-width: 800px; width: 100%;
                max-height: 90vh; max-height: 90dvh;
                overflow-y: auto; padding: 30px;
                position: relative; animation: modalIn 0.3s ease;
            }
            @keyframes modalIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .message-modal .modal-message .close-btn {
                position: absolute; top: 15px; right: 15px;
                background: #1e2a3a; border: none; color: #e4e9f2;
                width: 40px; height: 40px; border-radius: 50%;
                cursor: pointer; font-size: 20px;
                display: flex; align-items: center; justify-content: center;
                transition: all 0.3s; z-index: 10;
            }
            .message-modal .modal-message .close-btn:hover { background: #e74c3c; }
            .message-modal .modal-message .status-badge {
                position: absolute; top: 20px; right: 65px;
                padding: 3px 12px; border-radius: 20px;
                font-size: 10px; font-weight: 600;
                text-transform: uppercase; letter-spacing: 0.5px; z-index: 10;
            }
            .message-modal .modal-message .status-badge.history { background: #6c5ce7; color: white; }
            .message-modal .modal-message .status-badge.new { background: #00b894; color: white; animation: pulse 2s infinite; }
            .message-modal .modal-message .message-header {
                display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 20px; font-size: 14px;
                flex-wrap: wrap; gap: 10px; padding-right: 100px;
            }
            .message-modal .modal-message .message-chat {
                color: #00b894; font-weight: 600; font-size: 16px;
            }
            .message-modal .modal-message .message-source { color: #6c5ce7; font-weight: 600; }
            .message-modal .modal-message .message-date { color: #6a7a8e; }
            .message-modal .modal-message .message-text {
                font-size: 18px; line-height: 1.8; margin-bottom: 20px;
                word-wrap: break-word; overflow-wrap: break-word;
                white-space: pre-wrap;
            }
            .message-modal .modal-message .message-media img,
            .message-modal .modal-message .message-media video {
                max-width: 100%; max-height: 500px;
                border-radius: 12px; border: 1px solid #2a3a4a;
                height: auto;
            }
            .message-modal .modal-message .message-media video { max-height: 600px; }
            .message-modal .modal-message .message-tags {
                display: flex; gap: 8px; flex-wrap: wrap;
                margin-top: 20px; padding-top: 20px;
                border-top: 1px solid #1e2a3a;
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
                    padding: 16px 0; margin-bottom: 20px;
                }
                .header h1 { font-size: 20px; }
                .header h1 small { display: none; }
                .header-controls {
                    flex-direction: column; align-items: stretch; width: 100%;
                }
                .view-toggle { width: 100%; }
                .view-toggle button { flex: 1; justify-content: center; }
                .filters { grid-template-columns: 1fr; padding: 12px; gap: 8px; }
                .filters .filter-btn { width: 100%; justify-content: center; }
                .slider-container { padding: 16px; border-radius: 12px; }
                .slider-progress { font-size: 13px; margin-bottom: 16px; }
                .slider-message { padding: 18px; border-radius: 10px; }
                .slider-message .message-text { font-size: 16px; line-height: 1.6; }
                .slider-message .message-media img,
                .slider-message .message-media video { max-height: 240px; }
                .message-header { font-size: 12px; }
                .message-date { font-size: 11px; }
                .tag { font-size: 11px; padding: 3px 10px; }
                .slider-controls { flex-direction: row; gap: 10px; margin-top: 16px; }
                .slider-controls .nav-btn {
                    flex: 1; min-width: unset; padding: 12px 16px; font-size: 15px;
                }
                .list-message { padding: 16px; }
                .list-message .message-text { font-size: 14px; }
                .list-message .message-media img,
                .list-message .message-media video {
                    max-width: 150px; max-height: 120px;
                }
                .message-modal { padding: 0; align-items: flex-end; }
                .message-modal .modal-message {
                    border-radius: 20px 20px 0 0;
                    max-height: 92dvh;
                    padding: 24px 20px; border-bottom: none;
                }
                .message-modal .modal-message .close-btn {
                    width: 36px; height: 36px; font-size: 18px;
                }
                .message-modal .modal-message .status-badge {
                    top: 16px; right: 56px; font-size: 9px;
                }
                .message-modal .modal-message .message-header {
                    padding-right: 90px; font-size: 13px;
                }
                .message-modal .modal-message .message-text {
                    font-size: 16px; line-height: 1.7;
                }
                .message-modal .modal-message .message-media img,
                .message-modal .modal-message .message-media video { max-height: 300px; }
                .confirm-modal .modal-content { padding: 24px 20px; }
                .confirm-modal .modal-buttons { flex-direction: column; }
                .confirm-modal .modal-buttons button { width: 100%; }
            }
            @media (max-width: 380px) {
                body { padding: 8px; }
                .header h1 { font-size: 18px; }
                .view-toggle button { padding: 6px 10px; font-size: 12px; }
                .slider-message { padding: 14px; }
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
            ::-webkit-scrollbar { width: 8px; height: 8px; }
            ::-webkit-scrollbar-track { background: #0a0e1a; }
            ::-webkit-scrollbar-thumb { background: #2a3a4a; border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: #3a4a5a; }
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