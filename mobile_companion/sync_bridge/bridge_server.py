import os
import sys
import json
import time
import socket
import threading
from datetime import datetime
from flask import Flask, jsonify, request, Response, send_file

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

app = Flask(__name__)

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_bundle_dir():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return get_app_dir()

def get_apk_path():
    app_dir = get_app_dir()
    p1 = os.path.join(app_dir, "mobile_companion", "focusflow-companion.apk")
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(app_dir, "focusflow-companion.apk")
    if os.path.exists(p2):
        return p2
    bundle_dir = get_bundle_dir()
    p3 = os.path.join(bundle_dir, "mobile_companion", "focusflow-companion.apk")
    if os.path.exists(p3):
        return p3
    p4 = os.path.join(bundle_dir, "focusflow-companion.apk")
    if os.path.exists(p4):
        return p4
    return None

APP_DIR = get_app_dir()
DATA_FILE = os.path.join(APP_DIR, "focus_data.json")
LIVE_SESSION_FILE = os.path.join(APP_DIR, "focus_live_session.json")

# In-memory session state (mirrored to LIVE_SESSION_FILE for cross-process coordination)
session_lock = threading.Lock()
subscribers = []
subscribers_lock = threading.Lock()

def get_local_ip():
    """Finds the primary local LAN IP address to display to the user."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def load_focus_data():
    """Safely loads focus_data.json."""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Bridge] Error reading focus_data.json: {e}")
        return {}

def save_focus_data(data):
    """Safely writes back to focus_data.json."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        broadcast_event("data_updated", {"timestamp": time.time()})
        return True
    except Exception as e:
        print(f"[Bridge] Error saving focus_data.json: {e}")
        return False

def load_live_session():
    """Reads live session state (shared between Focus_app.pyw and bridge)."""
    if not os.path.exists(LIVE_SESSION_FILE):
        return {
            "is_active": False,
            "subject": "",
            "duration_minutes": 0,
            "started_at": 0,
            "target_end_at": 0,
            "remaining_seconds": 0,
            "is_paused": False,
            "is_overtime": False
        }
    try:
        with open(LIVE_SESSION_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            if state.get("is_active") and not state.get("is_paused"):
                now = time.time()
                remaining = max(0, int(state.get("target_end_at", now) - now))
                state["remaining_seconds"] = remaining
            return state
    except Exception:
        return {"is_active": False, "remaining_seconds": 0}

def save_live_session(state):
    try:
        with open(LIVE_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        broadcast_event("session_state", state)
    except Exception as e:
        print(f"[Bridge] Error saving live session: {e}")

def broadcast_event(event_name, data):
    """Sends SSE event to all connected Android/Web clients."""
    with subscribers_lock:
        dead = []
        payload = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
        for q in subscribers:
            try:
                q.put(payload)
            except Exception:
                dead.append(q)
        for d in dead:
            subscribers.remove(d)

def timer_ticker_thread():
    last_tick_active = False
    while True:
        time.sleep(1.0)
        with session_lock:
            state = load_live_session()
            if state.get("is_active"):
                last_tick_active = True
                now = time.time()
                target = state.get("target_end_at", now)
                rem = max(0, int(target - now))
                state["remaining_seconds"] = rem
                if rem == 0 and not state.get("is_overtime"):
                    broadcast_event("session_completed", state)
                else:
                    broadcast_event("session_tick", {
                        "remaining_seconds": rem,
                        "subject": state.get("subject", ""),
                        "is_active": True
                    })
            elif last_tick_active:
                last_tick_active = False
                broadcast_event("session_ended", {"is_active": False})

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Methods'] = 'GET,POST,OPTIONS'
    return response

@app.route("/", methods=["GET"])
def index():
    ip = get_local_ip()
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>FocusFlow Companion</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f13; color: #fff; text-align: center; padding: 40px 16px; margin: 0; }}
        .card {{ background: #181824; max-width: 420px; margin: 0 auto; padding: 28px 20px; border-radius: 20px; border: 1px solid #28283c; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
        h1 {{ font-size: 22px; margin: 0 0 6px 0; color: #fff; }}
        p {{ color: #9da0b5; font-size: 14px; margin: 0 0 20px 0; line-height: 1.4; }}
        .btn {{ display: block; background: #6366f1; color: white; padding: 15px 20px; border-radius: 12px; text-decoration: none; font-weight: bold; font-size: 16px; box-shadow: 0 4px 14px rgba(99,102,241,0.4); }}
        .steps {{ margin-top: 25px; text-align: left; display: flex; flex-direction: column; gap: 10px; }}
        .step {{ background: #202030; padding: 12px 14px; border-radius: 10px; font-size: 13px; color: #e0e0ee; border-left: 3px solid #6366f1; }}
        .badge {{ display: inline-block; background: #232338; color: #818cf8; padding: 4px 8px; border-radius: 6px; font-family: monospace; font-size: 13px; font-weight: bold; margin-top: 4px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>📱 FocusFlow Companion</h1>
        <p>Android companion for study timers, app blocker & Do Not Disturb.</p>
        <a class="btn" href="/download">⬇️ Download APK (6.6 MB)</a>
        <div class="steps">
            <div class="step"><b>1. Download &amp; Install:</b> Tap the button above to download. (If Play Protect warns about an unknown developer, tap <i>More details ▾ &rarr; Install anyway</i>).</div>
            <div class="step"><b>2. Grant Permissions:</b> Open FocusFlow and tap Enable on permissions.<br><i>⚠️ If Android 13/14 says "Restricted setting":</i> Open phone Settings &rarr; Apps &rarr; FocusFlow &rarr; tap 3 dots (⋮) &rarr; "Allow restricted settings".</div>
            <div class="step"><b>3. Sync to PC:</b> Enter this address in the top bar and tap <b>Sync</b>:<br><span class="badge">{ip}:5050</span></div>
        </div>
    </div>
</body>
</html>"""

@app.route("/download", methods=["GET"])
def download_apk():
    apk_path = get_apk_path()
    if apk_path and os.path.exists(apk_path):
        return send_file(apk_path, as_attachment=True, download_name="focusflow-companion.apk", mimetype="application/vnd.android.package-archive")
    return "focusflow-companion.apk not found", 404

@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({
        "status": "ok",
        "app": "FocusFlow Bridge",
        "version": "1.0",
        "server_time": time.time(),
        "local_ip": get_local_ip()
    })

@app.route("/api/version", methods=["GET"])
def get_version():
    apk_path = get_apk_path()
    size_mb = f"{os.path.getsize(apk_path) / (1024 * 1024):.1f} MB" if (apk_path and os.path.exists(apk_path)) else "6.2 MB"
    return jsonify({
        "versionCode": 9,
        "versionName": "1.0.8",
        "downloadUrl": "/download",
        "releaseNotes": "PC App Complete Modern UI Redesign, 3-Milestone Exam Tracking (Opens, Target, Closes), Moodle companion event detection",
        "apkSize": size_mb,
        "minSupportedVersion": 1
    })

@app.route("/api/status", methods=["GET"])
def get_status():
    """Returns complete state for the mobile companion."""
    data = load_focus_data()
    live = load_live_session()
    
    deadlines = data.get("deadlines", [])
    upcoming = [d for d in deadlines if not d.get("completed", False)]
    upcoming.sort(key=lambda x: x.get("due", "9999-99-99"))

    total_min = data.get("reward_tier_minutes", 0)
    ranks = data.get("ranks", [])
    next_rank = None
    for r in sorted(ranks, key=lambda x: x.get("threshold", 0)):
        if r.get("threshold", 0) > total_min:
            next_rank = r
            break

    return jsonify({
        "active_session": live,
        "streak_count": data.get("streak_count", 0),
        "total_minutes": data.get("total_minutes", 0),
        "reward_tier_minutes": total_min,
        "next_rank": next_rank,
        "ranks": ranks,
        "custom_tags": data.get("custom_tags", []),
        "tag_targets": data.get("tag_targets", {}),
        "upcoming_deadlines": upcoming[:10],
        "blocked_apps": data.get("blocked_apps", []),
        "pre_designated_session": data.get("pre_designated_session", {})
    })

@app.route("/api/session/start", methods=["POST"])
def start_session():
    req = request.get_json(force=True, silent=True) or {}
    minutes = int(req.get("minutes", 30))
    subject = req.get("subject", "#Focus")

    with session_lock:
        now = time.time()
        state = {
            "is_active": True,
            "subject": subject,
            "duration_minutes": minutes,
            "started_at": now,
            "target_end_at": now + (minutes * 60),
            "remaining_seconds": minutes * 60,
            "is_paused": False,
            "is_overtime": False
        }
        save_live_session(state)
        broadcast_event("session_started", state)

    return jsonify({"success": True, "session": state})

@app.route("/api/session/stop", methods=["POST"])
def stop_session():
    with session_lock:
        state = {
            "is_active": False,
            "subject": "",
            "duration_minutes": 0,
            "started_at": 0,
            "target_end_at": 0,
            "remaining_seconds": 0,
            "is_paused": False,
            "is_overtime": False
        }
        save_live_session(state)
        broadcast_event("session_stopped", state)

    return jsonify({"success": True, "session": state})

@app.route("/api/deadlines/toggle", methods=["POST"])
def toggle_deadline():
    req = request.get_json(force=True, silent=True) or {}
    uid = req.get("uid")
    if not uid:
        return jsonify({"success": False, "error": "Missing uid"}), 400

    data = load_focus_data()
    found = False
    for d in data.get("deadlines", []):
        if d.get("uid") == uid:
            d["completed"] = not d.get("completed", False)
            found = True
            break

    if found:
        save_focus_data(data)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Deadline not found"}), 404

@app.route("/api/pre_designate", methods=["POST"])
def pre_designate():
    req = request.get_json(force=True, silent=True) or {}
    data = load_focus_data()
    data["pre_designated_session"] = {
        "active": True,
        "date": req.get("date", datetime.now().strftime("%Y-%m-%d")),
        "time": req.get("time", "14:00"),
        "minutes": int(req.get("minutes", 60)),
        "subject": req.get("subject", "#Focus"),
        "warned_5m": False,
        "warned_3m": False,
        "warned_1m": False
    }
    save_focus_data(data)
    return jsonify({"success": True, "pre_designated": data["pre_designated_session"]})

@app.route("/api/events", methods=["GET"])
def sse_events():
    """Server-Sent Events endpoint for instant real-time Android push."""
    import queue
    q = queue.Queue(maxsize=100)
    with subscribers_lock:
        subscribers.append(q)

    def event_stream():
        yield f"event: connected\ndata: {json.dumps({'connected': True, 'time': time.time()})}\n\n"
        live = load_live_session()
        yield f"event: session_state\ndata: {json.dumps(live)}\n\n"
        while True:
            try:
                msg = q.get(timeout=20.0)
                yield msg
            except queue.Empty:
                yield ": heartbeat\n\n"

    return Response(event_stream(), mimetype="text/event-stream")

_ticker_started = False
_ticker_lock = threading.Lock()

def start_embedded_server(port=5050):
    """Runs Flask server quietly on 0.0.0.0:port on a background thread inside focus_app.exe."""
    global _ticker_started
    with _ticker_lock:
        if not _ticker_started:
            ticker = threading.Thread(target=timer_ticker_thread, daemon=True)
            ticker.start()
            _ticker_started = True

    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    try:
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True, use_reloader=False)
    except Exception as e:
        print(f"[FocusFlow Bridge] Server error: {e}")

if __name__ == "__main__":
    port = 5050
    ip = get_local_ip()
    print("=" * 60)
    print(" FocusFlow Companion Synchronization Bridge")
    print(f" Local PC URL:  http://localhost:{port}")
    print(f" Phone Wi-Fi URL: http://{ip}:{port}")
    print("=" * 60)

    start_embedded_server(port)
