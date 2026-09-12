import sys
import subprocess
import time
import math
import string
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
import winsound
import ctypes
import tempfile
import webbrowser
import re
import urllib.request
import ssl
import threading
from datetime import datetime, timedelta, date
from collections import Counter

# --- Application Info & Versioning ---
APP_VERSION = "1.0.2"
GITHUB_REPO = "caecitas-glitch/Study-focus-app"

def parse_version_str(v_str):
    nums = re.findall(r'\d+', str(v_str))
    return tuple(map(int, nums)) if nums else (0,)

# --- Directory & Environment Helper ---

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

# --- Admin Status Check & Relaunch ---
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def relaunch_as_admin(extra_args=None):
    try:
        if getattr(sys, 'frozen', False):
            exe = sys.executable
            args = extra_args if extra_args is not None else " ".join(f'"{arg}"' for arg in sys.argv[1:])
        else:
            exe = sys.executable
            target = os.path.abspath(sys.argv[0])
            rest = extra_args if extra_args is not None else " ".join(f'"{arg}"' for arg in sys.argv[1:])
            args = f'"{target}" {rest}'.strip()
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
        sys.exit(0)
    except Exception as e:
        messagebox.showerror("Elevation Error", f"Failed to relaunch as administrator: {e}")

# --- Safe Dependency Check ---
psutil = None
try:
    import psutil
except ImportError:
    if not getattr(sys, 'frozen', False):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "--quiet"])
            import psutil
        except Exception:
            psutil = None

MARKER_START = "# --- FOCUS APP BLOCK START ---"
MARKER_END = "# --- FOCUS APP BLOCK END ---"

DEFAULT_BLOCKED_APPS = [
    "steam.exe", 
    "Discord.exe", 
    "BsgLauncher.exe", 
    "RSI Launcher.exe", 
    "OculusClient.exe",
    "Client.exe",
    "OculusDash.exe"
]

DEFAULT_BLOCKED_WEBSITES = [
    "www.youtube.com", "youtube.com",
    "www.twitch.tv", "twitch.tv",
    "www.netflix.com", "netflix.com",
    "www.reddit.com", "reddit.com",
    "www.twitter.com", "twitter.com", "x.com",
    "www.instagram.com", "instagram.com",
    "www.tiktok.com", "tiktok.com",
    "www.facebook.com", "facebook.com",
    "discord.com", "discordapp.com",
    "store.steampowered.com", "steamcommunity.com",
    "robertsspaceindustries.com", "escapefromtarkov.com",
    "www.amazon.com", "amazon.com",
    "www.ebay.com", "ebay.com"
]

DEFAULT_RANKS = [
    {"name": "Tier 1", "threshold": 60, "reward": "Reward 1"},
    {"name": "Tier 2", "threshold": 180, "reward": "Reward 2"},
    {"name": "Tier 3", "threshold": 360, "reward": "Reward 3"},
    {"name": "Tier 4", "threshold": 600, "reward": "Reward 4"},
    {"name": "Tier 5", "threshold": 1200, "reward": "Reward 5"}
]

DEFAULT_TAGS = ["#Placeholder"]

DEFAULT_TARGETS = {
    "#Placeholder": 10.0
}

ACHIEVEMENT_DEFINITIONS = [
    {"id": "first_step", "icon": "🥉", "name": "First Step", "desc": "Complete your first focus session (15+ min)"},
    {"id": "deep_work", "icon": "🥈", "name": "Deep Work Master", "desc": "Complete a 60+ min focus session"},
    {"id": "centurion", "icon": "🥇", "name": "Centurion", "desc": "Reach 100 total focused hours"},
    {"id": "streak_king", "icon": "🔥", "name": "Consistency King", "desc": "Maintain a 5-day study streak"},
    {"id": "night_owl", "icon": "🦉", "name": "Night Scholar", "desc": "Complete a session after 10 PM"}
]

WELLNESS_TIPS = [
    "Hydrate! Grab a fresh glass of water.",
    "Rest your eyes! Look at something 20 feet away.",
    "Stand up and stretch your back & shoulders.",
    "Take 5 slow, deep breaths to reset your mind.",
    "Step away from your screen for a minute!"
]

YOUTUBE_RAIN_STREAM_URL = "https://www.youtube.com/watch?v=Qo4JIT8jMtI"

def get_youtube_embed_url(url):
    import re
    v_match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
    if v_match:
        return f"https://www.youtube.com/embed/{v_match.group(1)}?autoplay=1"
    short_match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url)
    if short_match:
        return f"https://www.youtube.com/embed/{short_match.group(1)}?autoplay=1"
    embed_match = re.search(r'youtube\.com/(?:live|embed)/([a-zA-Z0-9_-]{11})', url)
    if embed_match:
        return f"https://www.youtube.com/embed/{embed_match.group(1)}?autoplay=1"
    return url

# --- Spotify Launcher Helper ---
def launch_spotify_app():
    appdata = os.environ.get('APPDATA', '')
    localappdata = os.environ.get('LOCALAPPDATA', '')
    possible_paths = [
        os.path.join(localappdata, 'Microsoft', 'WindowsApps', 'Spotify.exe'),
        os.path.join(appdata, 'Spotify', 'Spotify.exe'),
        os.path.join(localappdata, 'Spotify', 'Spotify.exe'),
        r'C:\Program Files\Spotify\Spotify.exe',
        r'C:\Program Files (x86)\Spotify\Spotify.exe'
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path])
                return True
            except Exception:
                pass
    try:
        subprocess.Popen(['cmd', '/c', 'start', 'spotify:'], shell=True)
        return True
    except Exception:
        pass
    try:
        webbrowser.open("https://open.spotify.com")
        return True
    except Exception:
        return False

# --- Windows Startup Helper ---
def get_startup_shortcut_path():
    startup = os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs\Startup')
    return os.path.join(startup, 'FocusAppStartup.bat')

def set_windows_startup(enable=True):
    path = get_startup_shortcut_path()
    if enable:
        app_dir = get_app_dir()
        exe_candidate = os.path.join(app_dir, "focus_app.exe")
        target_exe = exe_candidate if os.path.exists(exe_candidate) else (os.path.abspath(sys.executable) if getattr(sys, 'frozen', False) else None)
        
        # If running as admin, also register an elevated scheduled task to run at logon without UAC prompt!
        if is_admin() and target_exe:
            try:
                subprocess.run(
                    f'schtasks /create /tn "FocusAppStartup" /tr "\\"{target_exe}\\" --startup-check" /sc onlogon /rl highest /f',
                    shell=True, capture_output=True
                )
            except Exception:
                pass

        if target_exe:
            cmd = f'cd /d "{app_dir}"\nstart "" "{target_exe}" --startup-check'
        else:
            pyw = sys.executable.replace("python.exe", "pythonw.exe")
            target = os.path.join(app_dir, "Focus_app.pyw")
            cmd = f'cd /d "{app_dir}"\nstart "" "{pyw}" "{target}" --startup-check'
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f'@echo off\n{cmd}\n')
            return True
        except Exception:
            return False
    else:
        try:
            subprocess.run('schtasks /delete /tn "FocusAppStartup" /f', shell=True, capture_output=True)
        except Exception:
            pass
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        return True

# --- iCal (.ics) Parser & URL Fetcher ---
def fetch_ical_from_url(url):
    clean_url = url.strip()
    if clean_url.startswith("webcal://"):
        clean_url = "https://" + clean_url[9:]
    elif clean_url.startswith("http://"):
        clean_url = "https://" + clean_url[7:]

    req = urllib.request.Request(
        clean_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')

def parse_ics_content(content):
    events = []
    lines = content.replace('\r\n', '\n').split('\n')
    
    unfolded_lines = []
    for line in lines:
        if line.startswith(' ') or line.startswith('\t'):
            if unfolded_lines:
                unfolded_lines[-1] += line[1:]
        else:
            unfolded_lines.append(line)
            
    in_event = False
    current_event = {}
    
    for line in unfolded_lines:
        line = line.strip()
        if line == 'BEGIN:VEVENT':
            in_event = True
            current_event = {"completed": False}
        elif line == 'END:VEVENT':
            if in_event and 'summary' in current_event and 'due' in current_event:
                events.append(current_event)
            in_event = False
        elif in_event and ':' in line:
            key_part, val = line.split(':', 1)
            key = key_part.split(';')[0].upper()
            
            if key == 'SUMMARY':
                current_event['summary'] = val.strip()
            elif key == 'UID':
                current_event['uid'] = val.strip()
            elif key in ('DTEND', 'DTSTART', 'DUE'):
                if 'due' not in current_event or key in ('DTEND', 'DUE'):
                    dt = parse_ics_date_str(val)
                    if dt:
                        current_event['due'] = dt.strftime('%Y-%m-%d')
    return events

def parse_ics_date_str(val):
    val = val.strip().replace('Z', '')
    for fmt in ('%Y%m%dT%H%M%S', '%Y%m%d'):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            pass
    m = re.search(r'(\d{8})', val)
    if m:
        try:
            return datetime.strptime(m.group(1), '%Y%m%d')
        except ValueError:
            pass
    return None

def merge_calendar_events(existing_deadlines, new_events):
    """
    Intelligently merges calendar events into existing deadlines:
    - Matches by UID if available.
    - Matches by summary for single-occurrence events (updating due date if rescheduled).
    - Matches by (summary, due) for repeating generic titles (e.g. attendance).
    - Preserves existing course tags and completion statuses.
    - Deduplicates multiple existing entries with identical summaries.
    - Preserves user-created manual tasks that are not in the calendar feed.
    Returns (merged_list, added_count, updated_count).
    """
    summary_counts = Counter(e.get("summary", "").strip().lower() for e in new_events)

    existing_tags = {}
    existing_completed = set()
    existing_attendance = set()
    for d in existing_deadlines:
        s_low = d.get("summary", "").strip().lower()
        if d.get("tag") and s_low not in existing_tags:
            existing_tags[s_low] = d["tag"]
        if d.get("completed"):
            existing_completed.add((s_low, d.get("due")))
        if d.get("is_attendance"):
            existing_attendance.add(s_low)

    merged = []
    used_existing = set()
    added_count = 0
    updated_count = 0

    for e in new_events:
        e_sum = e.get("summary", "").strip()
        s_low = e_sum.lower()
        is_recurring = summary_counts[s_low] > 1

        matched = None
        # 1. Match by UID
        if e.get("uid"):
            for idx, d in enumerate(existing_deadlines):
                if idx not in used_existing and d.get("uid") == e["uid"]:
                    matched = (idx, d)
                    break

        # 2. Match by summary for non-recurring assignments
        if not matched and not is_recurring:
            for idx, d in enumerate(existing_deadlines):
                if idx not in used_existing and d.get("summary", "").strip().lower() == s_low:
                    matched = (idx, d)
                    break

        # 3. Match by (summary, due) for recurring items
        if not matched and is_recurring:
            for idx, d in enumerate(existing_deadlines):
                if idx not in used_existing and d.get("summary", "").strip().lower() == s_low and d.get("due") == e.get("due"):
                    matched = (idx, d)
                    break

        completed = False
        tag = None
        is_attendance = False
        if matched:
            idx, d = matched
            used_existing.add(idx)
            completed = d.get("completed", False)
            tag = d.get("tag")
            is_attendance = d.get("is_attendance", False)
            if d.get("due") != e["due"]:
                updated_count += 1
        else:
            added_count += 1

        if not tag and s_low in existing_tags:
            tag = existing_tags[s_low]

        if not completed and (s_low, e.get("due")) in existing_completed:
            completed = True

        if not is_attendance and (s_low in existing_attendance or "läsnäolo" in s_low or "attendance" in s_low):
            is_attendance = True

        item = {
            "completed": completed,
            "summary": e["summary"],
            "due": e["due"],
            "uid": e.get("uid", ""),
            "is_attendance": is_attendance
        }
        if tag:
            item["tag"] = tag
        merged.append(item)

    # Preserve any manual tasks created by the user that were not in the calendar
    calendar_summaries = set(e.get("summary", "").strip().lower() for e in new_events)
    for idx, d in enumerate(existing_deadlines):
        if idx not in used_existing:
            s_low = d.get("summary", "").strip().lower()
            if s_low not in calendar_summaries:
                merged.append(d)

    merged.sort(key=lambda x: (x.get("completed", False), x.get("is_attendance", False), x["due"]))
    return merged, added_count, updated_count



# --- Flow Momentum Overtime Modal ---
class FlowMomentumWindow(tk.Toplevel):
    def __init__(self, parent, base_minutes, on_select_boost, on_finish, continuation_count=0, chain_total_minutes=None):
        super().__init__(parent)
        self.title("🔥 Ride the Flow State Momentum!")
        self.geometry("450x420")
        self.configure(bg="#0d0d15")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_select_boost = on_select_boost
        self.on_finish = on_finish
        self.continuation_count = continuation_count
        chain_total = chain_total_minutes if chain_total_minutes is not None else base_minutes

        next_continue_num = continuation_count + 1
        if next_continue_num == 1:
            stage_title = "🔥 Ride the Flow State! (Continue #1)"
            stage_desc = f"Completed {base_minutes}m. Extend your flow state for a Reward Tier Boost:"
        elif next_continue_num == 2:
            stage_title = "⚡ Double Continue Active! (Continue #2)"
            stage_desc = f"In the zone! {chain_total}m completed so far. Add a Double Continue:"
        else:
            stage_title = "🚀 Triple Continue! (Final Extension #3)"
            stage_desc = f"Peak momentum! {chain_total}m total so far. Final Triple Continue:"

        tk.Label(self, text=stage_title, font=("Segoe UI", 12, "bold"), bg="#0d0d15", fg="#ff9800").pack(pady=(16, 2))
        tk.Label(self, text=stage_desc, font=("Segoe UI", 8), bg="#0d0d15", fg="#cccccc", wraplength=410).pack(pady=(0, 10))

        # Scaling bonus multiplier for deeper continuation chains
        bonus_adder = 0.05 * continuation_count
        if base_minutes >= 75:
            options = [(20, round(1.20 + bonus_adder, 2)), (30, round(1.28 + bonus_adder, 2)), (45, round(1.33 + bonus_adder, 2)), (60, round(1.40 + bonus_adder, 2))]
        elif base_minutes >= 45:
            options = [(15, round(1.15 + bonus_adder, 2)), (30, round(1.25 + bonus_adder, 2)), (45, round(1.30 + bonus_adder, 2)), (60, round(1.35 + bonus_adder, 2))]
        else:
            options = [(15, round(1.12 + bonus_adder, 2)), (25, round(1.18 + bonus_adder, 2)), (30, round(1.20 + bonus_adder, 2)), (45, round(1.25 + bonus_adder, 2))]

        btn_container = tk.Frame(self, bg="#0d0d15")
        btn_container.pack(fill=tk.BOTH, expand=True, padx=25)

        for mins, mult in options:
            row = tk.Frame(btn_container, bg="#14141e", highlightbackground="#2d2d3f", highlightthickness=1)
            row.pack(fill=tk.X, pady=3)

            credit_mins = round(mins * mult, 1)
            bonus_str = f"+{credit_mins}m reward credit"

            tk.Label(row, text=f"+{mins} min", font=("Segoe UI", 10, "bold"), bg="#14141e", fg="#ffffff", width=8, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
            tk.Label(row, text=f"⚡ {mult}x Multiplier", font=("Segoe UI", 9, "bold"), bg="#14141e", fg="#00bcd4").pack(side=tk.LEFT, padx=5)
            tk.Label(row, text=f"({bonus_str})", font=("Segoe UI", 8), bg="#14141e", fg="#888888").pack(side=tk.LEFT, padx=5)

            btn = tk.Button(row, text="Select", font=("Segoe UI", 8, "bold"), bg="#00bcd4", fg="black", relief="flat", padx=10, command=lambda m=mins, x=mult: self.choose(m, x))
            btn.pack(side=tk.RIGHT, padx=10)

        finish_txt = f"✓ Finish Session ({chain_total}m Total — No More Boosts)" if continuation_count > 0 else "✓ Finish Session (No Boost)"
        finish_btn = tk.Button(self, text=finish_txt, font=("Segoe UI", 8, "bold"), bg="#222222", fg="#aaaaaa", relief="flat", pady=6, padx=12, command=self.finish)
        finish_btn.pack(pady=12)

        self.protocol("WM_DELETE_WINDOW", self.finish)

    def choose(self, mins, mult):
        self.destroy()
        self.on_select_boost(mins, mult)

    def finish(self):
        self.destroy()
        self.on_finish()


# --- Post-Session Metacognitive Reflection Modal ---
class PostSessionReflectionWindow(tk.Toplevel):
    def __init__(self, parent, session_info, on_save_callback=None):
        super().__init__(parent)
        self.title("🧠 Metacognitive Wrap-Up")
        self.geometry("520x660")
        self.configure(bg="#0d0d15")
        self.resizable(False, True)
        self.transient(parent)
        self.grab_set()

        self.session_info = session_info or {}
        self.on_save_callback = on_save_callback

        # State variables
        self.work_type_var = tk.StringVar(value="🧠 Deep Problem Solving")
        self.friction_var = tk.IntVar(value=1)
        self.friction_cause_var = tk.StringVar(value="None / Smooth")
        self.distraction_var = tk.StringVar(value="🎯 Pure Tunnel Vision")
        self.caffeine_var = tk.StringVar(value="None")
        self.sleep_var = tk.StringVar(value="Normal (6-8h)")
        self.outcome_var = tk.StringVar(value="✅ Hit Goal Cleanly")
        self.energy_var = tk.IntVar(value=3)
        self.focus_var = tk.IntVar(value=4)
        self.pacing_var = tk.StringVar(value="⏱️ As expected / Just right")

        # Header (Fixed)
        hdr = tk.Frame(self, bg="#0d0d15")
        hdr.pack(fill=tk.X, padx=16, pady=(12, 2))
        tk.Label(hdr, text="🧠 Metacognitive Wrap-Up", font=("Segoe UI", 12, "bold"), bg="#0d0d15", fg="#00bcd4").pack(anchor="w")
        tk.Label(hdr, text="Self-calibration questions for focus habits & session review:", font=("Segoe UI", 8), bg="#0d0d15", fg="#888888").pack(anchor="w", pady=(1, 0))

        # Session chip
        mins = self.session_info.get("minutes", 0)
        subj = self.session_info.get("subject", "#General")
        checks = self.session_info.get("clock_checks", 0)
        c_count = self.session_info.get("continuation_count", 0)
        chip_f = tk.Frame(self, bg="#161624", highlightbackground="#2d2d3f", highlightthickness=1)
        chip_f.pack(fill=tk.X, padx=16, pady=(4, 6))

        if c_count > 0:
            c_label = "Double Continued (x2)" if c_count == 2 else ("Triple Continued (x3)" if c_count >= 3 else "Continued (x1)")
            chip_txt = f"⏱️ Focused: {mins} mins ({c_label})  •  🏷️ Course: {subj}  •  🔒 Clock Checks: {checks}"
        else:
            chip_txt = f"⏱️ Focused: {mins} mins (Single Session)  •  🏷️ Course: {subj}  •  🔒 Clock Checks: {checks}"
        tk.Label(chip_f, text=chip_txt, font=("Segoe UI", 8, "bold"), bg="#161624", fg="#ff9800").pack(pady=4)

        # Scrollable container
        container = tk.Frame(self, bg="#0d0d15")
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 4))

        self.canvas = tk.Canvas(container, bg="#0d0d15", highlightthickness=0)
        sb = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scroll_body = tk.Frame(self.canvas, bg="#0d0d15")

        self.scroll_body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_body, anchor="nw", width=470)
        self.canvas.configure(yscrollcommand=sb.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel support
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.bind("<Destroy>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # --- Q1: Mental Work Type ---
        self.build_section_header("1. Mental Work Type (Active vs. Passive):")
        q1_opts = [
            ("🧠 Deep Problem Solving", "Calculations / Writing / Coding"),
            ("📖 Passive Input", "Reading / Videos / Lectures"),
            ("🗂️ Admin / Prep", "Planning / Organizing / Setup")
        ]
        self.q1_btns = self.create_button_group(self.scroll_body, q1_opts, self.work_type_var, "#00bcd4", is_tuple=True)

        # --- Q2: Goal Outcome Verdict ---
        self.build_section_header("2. Goal Outcome Verdict:")
        q2_opts = ["🏆 Exceeded Goal", "✅ Hit Goal Cleanly", "🔄 Partial Progress", "❌ Stuck / Derailed"]
        self.q2_btns = self.create_button_group(self.scroll_body, q2_opts, self.outcome_var, "#4CAF50")

        # --- Q3: Starting Friction ---
        self.build_section_header("3. Starting Friction (Activation Cost 1-5):")
        fric_levels = [
            (1, "1 🟢 Instant"),
            (2, "2 🟡 Low"),
            (3, "3 🟠 Medium"),
            (4, "4 🔴 Heavy"),
            (5, "5 🛑 High Dread")
        ]
        self.fric_btns = {}
        fric_row = tk.Frame(self.scroll_body, bg="#161624", highlightbackground="#252535", highlightthickness=1)
        fric_row.pack(fill=tk.X, pady=(0, 4))
        f_sub = tk.Frame(fric_row, bg="#161624")
        f_sub.pack(fill=tk.X, padx=4, pady=3)
        for val, txt in fric_levels:
            b = tk.Button(
                f_sub, text=txt, font=("Segoe UI", 7, "bold"),
                bg="#ff9800" if val == 1 else "#222230",
                fg="black" if val == 1 else "#bbbbbb",
                relief="flat", padx=2, pady=3,
                command=lambda v=val: self.set_friction_val(v)
            )
            b.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            self.fric_btns[val] = b

        tk.Label(self.scroll_body, text="Primary friction trigger (if any):", font=("Segoe UI", 7), bg="#0d0d15", fg="#888888").pack(anchor="w", pady=(0, 1))
        fric_causes = ["None / Smooth", "Ambiguous Task", "Felt Overwhelming", "Tired / Sleepy", "Distraction Urge"]
        self.fric_cause_btns = self.create_button_group(self.scroll_body, fric_causes, self.friction_cause_var, "#ff9800")

        # --- Q4: Distraction Audit ---
        self.build_section_header("4. Distraction & Attention Drift Audit:")
        dist_opts = ["🎯 Pure Tunnel Vision", "📱 Phone/Socials", "🌐 Web Browsing", "💭 Mental Drift", "👥 Interruption"]
        self.dist_btns = self.create_button_group(self.scroll_body, dist_opts, self.distraction_var, "#e91e63")

        # --- Q5: Focus Quality (1-5) & Energy (1-5) ---
        self.build_section_header("5. Focus Quality (1-5) & Energy (1-5):")
        foc_en_f = tk.Frame(self.scroll_body, bg="#161624", highlightbackground="#252535", highlightthickness=1)
        foc_en_f.pack(fill=tk.X, pady=(0, 4))

        f_row = tk.Frame(foc_en_f, bg="#161624")
        f_row.pack(fill=tk.X, padx=4, pady=3)
        tk.Label(f_row, text="Focus:", font=("Segoe UI", 7, "bold"), bg="#161624", fg="#00bcd4", width=7, anchor="w").pack(side=tk.LEFT)
        self.focus_btns = {}
        for val, txt in [(1, "1 😵"), (2, "2 📱"), (3, "3 🎯"), (4, "4 🧠 Flow"), (5, "5 🔥 Peak")]:
            b = tk.Button(f_row, text=txt, font=("Segoe UI", 7, "bold"), bg="#4CAF50" if val == 4 else "#222230", fg="white" if val == 4 else "#bbbbbb", relief="flat", padx=3, pady=2, command=lambda v=val: self.set_focus_val(v))
            b.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            self.focus_btns[val] = b

        e_row = tk.Frame(foc_en_f, bg="#161624")
        e_row.pack(fill=tk.X, padx=4, pady=(1, 4))
        tk.Label(e_row, text="Energy:", font=("Segoe UI", 7, "bold"), bg="#161624", fg="#ff9800", width=7, anchor="w").pack(side=tk.LEFT)
        self.energy_btns = {}
        for val, txt in [(1, "1 🪫"), (2, "2 📉"), (3, "3 ⚡"), (4, "4 🔋"), (5, "5 🚀 Peak")]:
            b = tk.Button(e_row, text=txt, font=("Segoe UI", 7, "bold"), bg="#00bcd4" if val == 3 else "#222230", fg="black" if val == 3 else "#bbbbbb", relief="flat", padx=3, pady=2, command=lambda v=val: self.set_energy_val(v))
            b.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            self.energy_btns[val] = b

        # --- Q6: Physical Calibration & Pacing ---
        self.build_section_header("6. Physical State (Caffeine & Sleep) & Pacing:")
        caff_opts = ["☕ No Caffeine", "☕ Coffee/Energy Drink", "☕ Crashed"]
        self.caff_btns = self.create_button_group(self.scroll_body, caff_opts, self.caffeine_var, "#795548")

        sleep_opts = ["🔋 Poor (<6h)", "🔋 Normal (6-8h)", "🔋 Well-Rested (8h+)"]
        self.sleep_btns = self.create_button_group(self.scroll_body, sleep_opts, self.sleep_var, "#3f51b5")

        pacing_opts = ["⚡ Shorter than expected", "⏱️ As expected / Just right", "⏳ Longer than expected"]
        self.pacing_btns = self.create_button_group(self.scroll_body, pacing_opts, self.pacing_var, "#009688")

        # --- Q7: Notes & Obstacles ---
        self.build_section_header("7. Notes & Obstacles:")
        
        # Tamper-proof Verified Clock Checks Row (Non-editable, cannot be deleted or cheated)
        lock_color = "#4CAF50" if checks == 0 else ("#ff9800" if checks <= 2 else "#f44336")
        lock_txt = "🔒 Verified Clock Checks: 0 (Pure focus — zero clock watching)" if checks == 0 else f"🔒 Verified Clock Checks: {checks} time(s) (Clock revealed during session • Locked)"
        lock_box = tk.Frame(self.scroll_body, bg="#14141e", highlightbackground=lock_color, highlightthickness=1)
        lock_box.pack(fill=tk.X, pady=(0, 5))
        tk.Label(lock_box, text=lock_txt, font=("Segoe UI", 8, "bold"), bg="#14141e", fg=lock_color).pack(anchor="w", padx=8, pady=4)

        self.notes_text = tk.Text(self.scroll_body, height=3, bg="#1a1a26", fg="#ffffff", insertbackground="white", font=("Segoe UI", 8), relief="flat", highlightbackground="#2d2d3f", highlightthickness=1)
        self.notes_text.pack(fill=tk.X, pady=(0, 6))

        # Action Buttons (Fixed Footer)
        act_f = tk.Frame(self, bg="#0d0d15")
        act_f.pack(fill=tk.X, padx=16, pady=(4, 12))

        tk.Button(act_f, text="💾 Save Reflection", font=("Segoe UI", 8, "bold"), bg="#00bcd4", fg="black", relief="flat", padx=12, pady=4, command=self.save_and_close).pack(side=tk.LEFT)
        self.copy_btn = tk.Button(act_f, text="📋 Export End Survey", font=("Segoe UI", 8, "bold"), bg="#222233", fg="#00bcd4", relief="flat", padx=10, pady=4, command=self.export_end_survey)
        self.copy_btn.pack(side=tk.LEFT, padx=6)
        tk.Button(act_f, text="Skip", font=("Segoe UI", 8), bg="#1f1f1f", fg="#888888", relief="flat", padx=8, pady=4, command=self.destroy).pack(side=tk.RIGHT)

    def build_section_header(self, text):
        tk.Label(self.scroll_body, text=text, font=("Segoe UI", 8, "bold"), bg="#0d0d15", fg="#ffffff").pack(anchor="w", pady=(5, 2))

    def create_button_group(self, parent, options, target_var, active_bg, is_tuple=False):
        frame = tk.Frame(parent, bg="#161624", highlightbackground="#252535", highlightthickness=1)
        frame.pack(fill=tk.X, pady=(0, 4))
        btn_dict = {}
        row = tk.Frame(frame, bg="#161624")
        row.pack(fill=tk.X, padx=4, pady=3)

        def make_select(val):
            def select_action():
                target_var.set(val)
                for v, b in btn_dict.items():
                    if v == val:
                        b.config(bg=active_bg, fg="black" if active_bg in ("#00bcd4", "#ff9800") else "white")
                    else:
                        b.config(bg="#222230", fg="#bbbbbb")
            return select_action

        for opt in options:
            val = opt[0] if is_tuple else opt
            lbl = opt[0] if is_tuple else opt
            is_active = (target_var.get() == val)
            b = tk.Button(
                row, text=lbl, font=("Segoe UI", 7, "bold"),
                bg=active_bg if is_active else "#222230",
                fg="black" if (is_active and active_bg in ("#00bcd4", "#ff9800")) else ("white" if is_active else "#bbbbbb"),
                relief="flat", padx=3, pady=3,
                command=make_select(val)
            )
            b.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            btn_dict[val] = b
        return btn_dict

    def set_friction_val(self, val):
        self.friction_var.set(val)
        for v, b in self.fric_btns.items():
            if v == val:
                b.config(bg="#ff9800", fg="black")
            else:
                b.config(bg="#222230", fg="#bbbbbb")

    def set_focus_val(self, val):
        self.focus_var.set(val)
        for v, b in self.focus_btns.items():
            if v == val:
                b.config(bg="#4CAF50", fg="white")
            else:
                b.config(bg="#222230", fg="#bbbbbb")

    def set_energy_val(self, val):
        self.energy_var.set(val)
        for v, b in self.energy_btns.items():
            if v == val:
                b.config(bg="#00bcd4", fg="black")
            else:
                b.config(bg="#222230", fg="#bbbbbb")

    def get_reflection_dict(self):
        return {
            "work_type": self.work_type_var.get(),
            "goal_outcome": self.outcome_var.get(),
            "starting_friction": self.friction_var.get(),
            "friction_trigger": self.friction_cause_var.get(),
            "distraction_audit": self.distraction_var.get(),
            "focus_quality": self.focus_var.get(),
            "energy_level": self.energy_var.get(),
            "caffeine": self.caffeine_var.get(),
            "sleep": self.sleep_var.get(),
            "clock_checks": self.session_info.get("clock_checks", 0),
            "continuation_count": self.session_info.get("continuation_count", 0),
            "pacing": self.pacing_var.get(),
            "notes": self.notes_text.get("1.0", tk.END).strip(),
            "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

    def export_end_survey(self):
        ref = self.get_reflection_dict()
        mins = self.session_info.get("minutes", 0)
        subj = self.session_info.get("subject", "#Placeholder")
        checks = ref.get("clock_checks", 0)
        c_count = self.session_info.get("continuation_count", 0)

        if c_count > 0:
            c_tag = "Double Continued (x2)" if c_count == 2 else ("Triple Continued (x3)" if c_count >= 3 else "Continued (x1)")
            st_str = f"Continued Session ({c_tag})"
        else:
            st_str = "Single Session (Fresh start)"

        txt = (
            f"### 📋 Study Session End Survey\n"
            f"- **Subject**: {subj}\n"
            f"- **Duration**: {mins} minutes\n"
            f"- **Session Type**: {st_str}\n"
            f"- **Work Type**: {ref['work_type']}\n"
            f"- **Goal Outcome**: {ref['goal_outcome']}\n"
            f"- **Focus Quality**: {ref['focus_quality']}/5\n"
            f"- **Energy Level**: {ref['energy_level']}/5\n"
            f"- **Starting Friction**: {ref['starting_friction']}/5 ({ref['friction_trigger']})\n"
            f"- **Distraction Audit**: {ref['distraction_audit']}\n"
            f"- **Physical State**: {ref['caffeine']} | {ref['sleep']}\n"
            f"- **Clock Checks**: {checks} time(s) (verified uncheatable)\n"
            f"- **Task Pacing**: {ref['pacing']}\n"
        )
        if ref['notes']:
            txt += f"- **Notes / Blockers**: {ref['notes']}\n"
        self.clipboard_clear()
        self.clipboard_append(txt)
        self.copy_btn.config(text="✓ Exported!", fg="#4CAF50")

    copy_for_gemini = export_end_survey

    def save_and_close(self):
        ref = self.get_reflection_dict()
        if self.on_save_callback:
            self.on_save_callback(ref)
        self.destroy()


# --- Pre-Designate Session Dialog ---
class PreDesignateWindow(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("📅 Pre-Designate Focus Session")
        self.geometry("380x320")
        self.configure(bg="#121212")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text="📅 Pre-Schedule Next Session", font=("Segoe UI", 11, "bold"), bg="#121212", fg="#00bcd4").pack(pady=(15, 4))
        tk.Label(self, text="Lock in your study commitment in advance.\nThe app will FORCE-START this session on that day!", font=("Segoe UI", 8), bg="#121212", fg="#888888", justify="center").pack(pady=(0, 10))

        form_f = tk.Frame(self, bg="#1a1a1a")
        form_f.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        # Date Option
        tk.Label(form_f, text="Schedule Date:", font=("Segoe UI", 8, "bold"), bg="#1a1a1a", fg="#cccccc").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        self.date_var = tk.StringVar(value="Tomorrow")
        tomorrow_str = (datetime.now().date() + timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = datetime.now().date().strftime("%Y-%m-%d")
        date_combo = ttk.Combobox(form_f, textvariable=self.date_var, values=["Tomorrow (" + tomorrow_str + ")", "Today (" + today_str + ")"], state="readonly", font=("Segoe UI", 8))
        date_combo.grid(row=0, column=1, sticky="ew", padx=10, pady=8)

        # Duration Option
        tk.Label(form_f, text="Duration (Mins):", font=("Segoe UI", 8, "bold"), bg="#1a1a1a", fg="#cccccc").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        self.dur_var = tk.IntVar(value=45)
        dur_combo = ttk.Combobox(form_f, textvariable=self.dur_var, values=[15, 25, 30, 45, 60, 90, 120], state="readonly", font=("Segoe UI", 8))
        dur_combo.grid(row=1, column=1, sticky="ew", padx=10, pady=8)

        # Subject Tag Option
        tk.Label(form_f, text="Subject Tag:", font=("Segoe UI", 8, "bold"), bg="#1a1a1a", fg="#cccccc").grid(row=2, column=0, sticky="w", padx=10, pady=8)
        self.tag_var = tk.StringVar(value=self.app.custom_tags[0] if self.app.custom_tags else "#Placeholder")
        tag_combo = ttk.Combobox(form_f, textvariable=self.tag_var, values=self.app.custom_tags, state="readonly", font=("Segoe UI", 8))
        tag_combo.grid(row=2, column=1, sticky="ew", padx=10, pady=8)

        form_f.columnconfigure(1, weight=1)

        # Save Button
        tk.Button(self, text="🔒 Lock In Pre-Scheduled Session", font=("Segoe UI", 9, "bold"), bg="#4CAF50", fg="white", relief="flat", padx=10, pady=5, command=self.save_schedule).pack(pady=12)

    def save_schedule(self):
        choice = self.date_var.get()
        if "Tomorrow" in choice:
            sched_date = (datetime.now().date() + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            sched_date = datetime.now().date().strftime("%Y-%m-%d")

        self.app.pre_designated_session = {
            "active": True,
            "date": sched_date,
            "minutes": self.dur_var.get(),
            "subject": self.tag_var.get()
        }
        self.app.save_data()
        messagebox.showinfo("Session Locked In! 🔒", f"Pre-scheduled {self.dur_var.get()}m session for [{self.tag_var.get()}] on {sched_date}.\n\nThe app will force-start your session when launched on that day!")
        self.destroy()


# --- Upcoming Deadlines Popup Window ---
class UpcomingDeadlinesWindow(tk.Toplevel):
    def __init__(self, parent, deadlines, app=None, on_start_focus=None, on_dismiss_callback=None):
        super().__init__(parent)
        self.app = app
        self.title("🚨 Upcoming Assignment Deadlines")
        self.geometry("520x460")
        self.configure(bg="#0d0d15")
        self.resizable(False, False)
        self.on_dismiss_callback = on_dismiss_callback

        header_frame = tk.Frame(self, bg="#0d0d15")
        header_frame.pack(fill=tk.X, padx=15, pady=(15, 8))

        tk.Label(header_frame, text="🚨 Upcoming Deadlines (< 7 Days Left)", font=("Segoe UI", 12, "bold"), bg="#0d0d15", fg="#ff9800").pack(anchor="w")
        tk.Label(header_frame, text="Stay on top of coursework! Mark assignments done [✓] or remove [🗑️]:", font=("Segoe UI", 8), bg="#0d0d15", fg="#888888").pack(anchor="w", pady=(2, 0))

        list_container = tk.Frame(self, bg="#14141e")
        list_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=6)

        canvas = tk.Canvas(list_container, bg="#14141e", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#14141e")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=470)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        today = datetime.now().date()

        for item in deadlines:
            due_date = datetime.strptime(item["due"], "%Y-%m-%d").date()
            days_left = (due_date - today).days

            if days_left < 0:
                badge_txt = f"❌ Overdue {abs(days_left)}d!"
                badge_bg = "#b71c1c"
            elif days_left == 0:
                badge_txt = "🚨 DUE TODAY!"
                badge_bg = "#e53935"
            elif days_left == 1:
                badge_txt = "🔥 Due Tomorrow!"
                badge_bg = "#f57c00"
            else:
                badge_txt = f"⚠️ Due in {days_left}d"
                badge_bg = "#fbc02d"

            row = tk.Frame(scrollable_frame, bg="#1c1c28", highlightbackground="#2d2d3f", highlightthickness=1)
            row.pack(fill=tk.X, pady=4, padx=5)

            info_f = tk.Frame(row, bg="#1c1c28")
            info_f.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)

            tk.Label(info_f, text=item["summary"], font=("Segoe UI", 9, "bold"), bg="#1c1c28", fg="#ffffff", wraplength=260, justify="left").pack(anchor="w")
            tk.Label(info_f, text=f"Due Date: {item['due']}", font=("Segoe UI", 8), bg="#1c1c28", fg="#888888").pack(anchor="w")

            # Course tag dropdown for this deadline
            if self.app and hasattr(self.app, 'custom_tags'):
                tag_row = tk.Frame(info_f, bg="#1c1c28")
                tag_row.pack(anchor="w", pady=(2, 0))
                tk.Label(tag_row, text="Course:", font=("Segoe UI", 7, "bold"), bg="#1c1c28", fg="#00bcd4").pack(side=tk.LEFT, padx=(0, 3))
                tag_cb = ttk.Combobox(tag_row, values=["-- None --"] + self.app.custom_tags, width=19, state="readonly", font=("Segoe UI", 7))
                cur_tag = item.get("tag")
                if cur_tag and cur_tag in self.app.custom_tags:
                    tag_cb.set(cur_tag)
                else:
                    tag_cb.set("-- None --")
                def on_tag_changed(event, it=item, cb=tag_cb):
                    val = cb.get()
                    if val in self.app.custom_tags:
                        it["tag"] = val
                    else:
                        it.pop("tag", None)
                    if self.app:
                        self.app.save_data()
                        if hasattr(self.app, 'update_imminent_deadline_banner'):
                            self.app.update_imminent_deadline_banner()
                tag_cb.bind("<<ComboboxSelected>>", on_tag_changed)
                tag_cb.pack(side=tk.LEFT)

            ctrl_f = tk.Frame(row, bg="#1c1c28")
            ctrl_f.pack(side=tk.RIGHT, padx=6, pady=4)

            badge_fg = "black" if badge_bg == "#fbc02d" else "white"
            tk.Label(ctrl_f, text=badge_txt, font=("Segoe UI", 7, "bold"), bg=badge_bg, fg=badge_fg, padx=5, pady=2).pack(side=tk.TOP, anchor="e", pady=(0, 3))

            btn_row = tk.Frame(ctrl_f, bg="#1c1c28")
            btn_row.pack(side=tk.BOTTOM, anchor="e")

            def mark_done(it=item, r=row):
                it["completed"] = True
                if self.app:
                    self.app.save_data()
                r.destroy()

            def del_deadline(it=item, r=row):
                if self.app and it in self.app.deadlines:
                    self.app.deadlines.remove(it)
                    self.app.save_data()
                r.destroy()

            tk.Button(btn_row, text="✓ Done", font=("Segoe UI", 7, "bold"), bg="#2e7d32", fg="white", relief="flat", padx=4, pady=1, command=mark_done).pack(side=tk.LEFT, padx=2)
            tk.Button(btn_row, text="🗑️", font=("Segoe UI", 7), bg="#333333", fg="#f44336", relief="flat", padx=3, pady=1, command=del_deadline).pack(side=tk.LEFT, padx=2)

        action_bar = tk.Frame(self, bg="#0d0d15")
        action_bar.pack(fill=tk.X, padx=15, pady=12)

        if on_start_focus:
            tk.Button(action_bar, text="🚀 Open Focus Session", font=("Segoe UI", 9, "bold"), bg="#4CAF50", fg="white", relief="flat", padx=10, pady=4, command=lambda: [self.destroy(), on_start_focus()]).pack(side=tk.RIGHT, padx=5)

        tk.Button(action_bar, text="Dismiss", font=("Segoe UI", 9), bg="#222222", fg="#cccccc", relief="flat", padx=10, pady=4, command=self.dismiss).pack(side=tk.RIGHT, padx=5)
        self.protocol("WM_DELETE_WINDOW", self.dismiss)

    def dismiss(self):
        self.destroy()
        if self.on_dismiss_callback:
            self.on_dismiss_callback()


# --- Settings, Analytics, Deadlines & Dynamic Tags Modal ---
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Settings, Analytics & Deadlines")
        self.geometry("500x720")
        self.configure(bg="#121212")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background="#121212", borderwidth=0)
        style.configure("TNotebook.Tab", background="#1f1f1f", foreground="#cccccc", padding=[7, 5])
        style.map("TNotebook.Tab", background=[("selected", "#00bcd4")], foreground=[("selected", "#000000")])

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Analytics & Target Hours
        analytics_tab = tk.Frame(notebook, bg="#121212")
        notebook.add(analytics_tab, text="Analytics")
        self.setup_analytics_tab(analytics_tab)

        # Tab 2: Custom Tags
        tags_tab = tk.Frame(notebook, bg="#121212")
        notebook.add(tags_tab, text="Tags")
        self.setup_tags_tab(tags_tab)

        # Tab 3: Deadlines & iCal
        deadlines_tab = tk.Frame(notebook, bg="#121212")
        notebook.add(deadlines_tab, text="Deadlines")
        self.setup_deadlines_tab(deadlines_tab)

        # Tab 4: Rewards
        reward_tab = tk.Frame(notebook, bg="#121212")
        notebook.add(reward_tab, text="Rewards")
        self.setup_rewards_tab(reward_tab)

        # Tab 5: Badges
        badges_tab = tk.Frame(notebook, bg="#121212")
        notebook.add(badges_tab, text="Badges")
        self.setup_badges_tab(badges_tab)

        # Tab 6: Websites & Apps
        block_tab = tk.Frame(notebook, bg="#121212")
        notebook.add(block_tab, text="Blocker")
        self.setup_blocker_tab(block_tab)

        # Bottom Bar: Version & Auto-Update Check
        bottom_bar = tk.Frame(self, bg="#121212")
        bottom_bar.pack(fill=tk.X, padx=14, pady=(0, 10))
        tk.Label(bottom_bar, text=f"FocusFlow v{APP_VERSION}", font=("Segoe UI", 8), bg="#121212", fg="#777777").pack(side=tk.LEFT)
        tk.Button(
            bottom_bar,
            text="🔄 Check for Updates",
            font=("Segoe UI", 8, "bold"),
            bg="#1f1f1f",
            fg="#00bcd4",
            activebackground="#2a2a2a",
            activeforeground="#00bcd4",
            relief="flat",
            padx=8,
            pady=2,
            command=lambda: self.app.check_for_updates(silent=False)
        ).pack(side=tk.RIGHT)


    # --- Tab 1: Analytics, Weekly Heatmap & Course Balance ---
    def setup_analytics_tab(self, frame):
        tk.Label(frame, text="📊 Focus Analytics & Study Breakdown", font=("Segoe UI", 10, "bold"), bg="#121212", fg="#00bcd4").pack(anchor="w", pady=(8, 2), padx=10)
        
        history = self.app.history
        total_sessions = len(history)
        completed_sessions = sum(1 for h in history if h.get("completed", True))
        rate = round((completed_sessions / total_sessions * 100)) if total_sessions > 0 else 100
        avg_mins = round(sum(h.get("minutes", 0) for h in history) / total_sessions) if total_sessions > 0 else 0

        metrics_frame = tk.Frame(frame, bg="#1a1a1a")
        metrics_frame.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(metrics_frame, text=f"Sessions: {total_sessions} ({rate}% Completed)  |  Avg: {avg_mins}m  |  Total: {self.app.format_total_time()}", font=("Segoe UI", 8, "bold"), bg="#1a1a1a", fg="#ffffff").pack(pady=4)

        today = datetime.now().date()
        this_mon = today - timedelta(days=today.weekday())
        last_mon = this_mon - timedelta(days=7)
        this_sun = this_mon + timedelta(days=6)
        last_sun = this_mon - timedelta(days=1)

        this_week_mins = 0
        last_week_mins = 0
        mon_sun_mins = { (this_mon + timedelta(days=i)).strftime("%Y-%m-%d"): 0 for i in range(7) }

        for h in history:
            d_str = h.get("date", "")
            mins = h.get("minutes", 0)
            if this_mon.strftime("%Y-%m-%d") <= d_str <= this_sun.strftime("%Y-%m-%d"):
                this_week_mins += mins
                if d_str in mon_sun_mins:
                    mon_sun_mins[d_str] += mins
            elif last_mon.strftime("%Y-%m-%d") <= d_str <= last_sun.strftime("%Y-%m-%d"):
                last_week_mins += mins

        this_week_hrs = round(this_week_mins / 60.0, 1)
        last_week_hrs = round(last_week_mins / 60.0, 1)
        if this_week_hrs > last_week_hrs:
            trend_str = f"▲ +{round(this_week_hrs - last_week_hrs, 1)}h vs last week"
            trend_fg = "#4caf50"
        elif this_week_hrs < last_week_hrs:
            trend_str = f"▼ -{round(last_week_hrs - this_week_hrs, 1)}h vs last week"
            trend_fg = "#f44336"
        else:
            trend_str = "Equal to last week"
            trend_fg = "#aaaaaa"

        # Weekly Activity Header
        week_hdr = tk.Frame(frame, bg="#121212")
        week_hdr.pack(fill=tk.X, padx=10, pady=(4, 1))
        tk.Label(week_hdr, text=f"📅 This Week (Mon-Sun): {this_week_hrs}h", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#00bcd4").pack(side=tk.LEFT)
        tk.Label(week_hdr, text=f"({trend_str})", font=("Segoe UI", 8), bg="#121212", fg=trend_fg).pack(side=tk.LEFT, padx=5)

        # Mon-Sun 7-Day Bar Chart
        chart_canvas = tk.Canvas(frame, width=470, height=95, bg="#1a1a1a", highlightthickness=0)
        chart_canvas.pack(padx=10, pady=2)

        days_sorted = sorted(mon_sun_mins.keys())
        max_mins = max(max(mon_sun_mins.values(), default=60), 60)

        bar_width = 38
        gap = 24
        start_x = 24
        chart_height = 58

        for i, d_str in enumerate(days_sorted):
            mins = mon_sun_mins[d_str]
            x1 = start_x + i * (bar_width + gap)
            x2 = x1 + bar_width
            
            bar_h = int((mins / max_mins) * chart_height)
            y2 = 72
            y1 = y2 - max(3, bar_h)

            d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
            is_today = (d_obj == today)

            if is_today:
                bar_color = "#ff9800" if mins > 0 else "#443311"
            elif mins > 0:
                bar_color = "#00bcd4"
            else:
                bar_color = "#262626"

            chart_canvas.create_rectangle(x1, y1, x2, y2, fill=bar_color, outline="")
            if mins > 0:
                chart_canvas.create_text((x1 + x2)/2, y1 - 6, text=f"{mins}m", font=("Segoe UI", 7, "bold"), fill=bar_color)
                
            day_lbl = d_obj.strftime("%a") + ("*" if is_today else "")
            day_fg = "#ff9800" if is_today else "#888888"
            chart_canvas.create_text((x1 + x2)/2, 84, text=day_lbl, font=("Segoe UI", 7, "bold" if is_today else "normal"), fill=day_fg)

        # Course Study Balance Breakdown
        tag_mins = {t: 0 for t in self.app.custom_tags}
        for h in history:
            tag = h.get("subject", "#General")
            if tag in tag_mins:
                tag_mins[tag] += h.get("minutes", 0)
            else:
                tag_mins[tag] = h.get("minutes", 0)

        total_tracked = sum(tag_mins.values())

        bal_frame = tk.Frame(frame, bg="#121212")
        bal_frame.pack(fill=tk.X, padx=10, pady=(6, 2))
        tk.Label(bal_frame, text="⚖️ Course Study Balance Breakdown:", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#00bcd4").pack(side=tk.LEFT)

        palette = ["#00bcd4", "#4caf50", "#ff9800", "#ab47bc", "#e91e63", "#00b0ff", "#ffc107", "#8bc34a", "#9c27b0"]
        
        # Segmented Progress Bar
        bal_canvas = tk.Canvas(frame, width=470, height=12, bg="#1a1a1a", highlightthickness=0)
        bal_canvas.pack(padx=10, pady=2)

        cur_x = 0
        total_w = 470
        legend_items = []

        if total_tracked > 0:
            for idx, tag in enumerate(self.app.custom_tags):
                tm = tag_mins.get(tag, 0)
                if tm > 0:
                    pct = tm / total_tracked
                    seg_w = max(1, int(pct * total_w))
                    color = palette[idx % len(palette)]
                    bal_canvas.create_rectangle(cur_x, 0, min(total_w, cur_x + seg_w), 12, fill=color, outline="")
                    cur_x += seg_w
                    pct_int = int(round(pct * 100))
                    legend_items.append((tag, color, pct_int, round(tm / 60.0, 1)))
        else:
            bal_canvas.create_text(235, 6, text="No study history logged yet", font=("Segoe UI", 7), fill="#666666")

        if legend_items:
            legend_f = tk.Frame(frame, bg="#14141e")
            legend_f.pack(fill=tk.X, padx=10, pady=2)
            cur_lf = tk.Frame(legend_f, bg="#14141e")
            cur_lf.pack(fill=tk.X, pady=1)
            for i, (t, col, p, hrs) in enumerate(legend_items):
                if i > 0 and i % 3 == 0:
                    cur_lf = tk.Frame(legend_f, bg="#14141e")
                    cur_lf.pack(fill=tk.X, pady=1)
                tk.Label(cur_lf, text=f"■ {t}: {p}% ({hrs}h)", font=("Segoe UI", 7, "bold"), bg="#14141e", fg=col).pack(side=tk.LEFT, padx=6)

        # Custom Tag Targets & Hourly Goals Section
        tk.Label(frame, text="🏷️ Custom Course Targets & Hours Studied:", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#aaaaaa").pack(anchor="w", padx=10, pady=(6, 2))
        
        target_container = tk.Frame(frame, bg="#121212")
        target_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

        self.target_entries = {}
        for tag in self.app.custom_tags:
            row = tk.Frame(target_container, bg="#1a1a1a")
            row.pack(fill=tk.X, pady=2)

            hrs_studied = round(tag_mins.get(tag, 0) / 60.0, 1)
            target_hrs = float(self.app.tag_targets.get(tag, 10.0))
            pct = min(100, int((hrs_studied / target_hrs) * 100)) if target_hrs > 0 else 100

            tk.Label(row, text=f"{tag}:", font=("Segoe UI", 8, "bold"), bg="#1a1a1a", fg="#00bcd4", width=14, anchor="w").pack(side=tk.LEFT, padx=6)
            tk.Label(row, text=f"{hrs_studied}h /", font=("Segoe UI", 8), bg="#1a1a1a", fg="#ffffff").pack(side=tk.LEFT)

            t_ent = tk.Entry(row, width=4, font=("Segoe UI", 8, "bold"), bg="#262626", fg="white", justify="center", bd=0)
            t_ent.insert(0, str(int(target_hrs) if target_hrs.is_integer() else target_hrs))
            t_ent.pack(side=tk.LEFT, padx=2)
            tk.Label(row, text="h", font=("Segoe UI", 8), bg="#1a1a1a", fg="#888888").pack(side=tk.LEFT)

            self.target_entries[tag] = t_ent

            p_canv = tk.Canvas(row, width=100, height=8, bg="#262626", highlightthickness=0)
            p_canv.pack(side=tk.LEFT, padx=8)
            fill_w = max(1, int(100 * (pct / 100.0)))
            p_canv.create_rectangle(0, 0, fill_w, 8, fill="#4CAF50" if pct >= 100 else "#00bcd4", outline="")

            tk.Label(row, text=f"{pct}%", font=("Segoe UI", 8, "bold"), bg="#1a1a1a", fg="#aaaaaa", width=5).pack(side=tk.LEFT)

        btn_row = tk.Frame(frame, bg="#121212")
        btn_row.pack(fill=tk.X, padx=10, pady=4)
        tk.Button(btn_row, text="📋 Export End Surveys", font=("Segoe UI", 8, "bold"), bg="#1a1a2e", fg="#00bcd4", relief="flat", padx=8, pady=2, command=self.export_end_surveys).pack(side=tk.LEFT)
        tk.Button(btn_row, text="💾 Save Target Hours", font=("Segoe UI", 8, "bold"), bg="#00bcd4", fg="black", relief="flat", padx=8, pady=2, command=self.save_targets).pack(side=tk.RIGHT)

    def export_end_surveys(self):
        reflections = []
        for h in self.app.history:
            if "reflection" in h:
                ref = h["reflection"]
                wt = ref.get('work_type', 'N/A')
                outcome = ref.get('goal_outcome', 'N/A')
                fric = f"{ref.get('starting_friction', '?')}/5 ({ref.get('friction_trigger', 'N/A')})" if 'starting_friction' in ref else "N/A"
                dist = ref.get('distraction_audit', 'N/A')
                foc = ref.get('focus_quality', ref.get('focus', '?'))
                en = ref.get('energy_level', ref.get('energy', '?'))
                phys = f"{ref.get('caffeine', 'None')} | {ref.get('sleep', 'N/A')}" if 'caffeine' in ref else "N/A"
                cc = ref.get('clock_checks', 0)
                notes_str = f"\n  • Notes: {ref.get('notes')}" if ref.get("notes") else ""

                c_info = ""
                c_num = h.get("continuation_count", ref.get("continuation_count", 0))
                if h.get("is_continuation") or c_num > 0:
                    c_tag = "Double Continued (x2)" if c_num == 2 else ("Triple Continued (x3)" if c_num >= 3 else f"Continued x{c_num}")
                    chain_m = h.get("chain_total_minutes", h.get("minutes", 0))
                    c_info = f" [{c_tag} • Total Chain: {chain_m}m]"

                reflections.append(
                    f"- **{h.get('date', '')}** ({h.get('minutes', 0)}m on {h.get('subject', '#General')}{c_info}):\n"
                    f"  • Work Type: {wt} | Outcome: {outcome}\n"
                    f"  • Focus: {foc}/5 | Energy: {en}/5 | Friction: {fric}\n"
                    f"  • Distraction: {dist} | Physical: {phys} | Clock Checks: {cc} (locked)\n"
                    f"  • Pacing: {ref.get('pacing', 'N/A')}{notes_str}"
                )
        if not reflections:
            messagebox.showinfo("No Surveys Yet", "No post-session end surveys logged yet.\nComplete a focus session to record your first survey!")
            return
        output = "### 📋 Study Session End Surveys (Metacognitive History)\n\n" + "\n\n".join(reflections)
        self.clipboard_clear()
        self.clipboard_append(output)
        messagebox.showinfo("Copied! 📋", f"Copied {len(reflections)} end survey(s) to clipboard!\nYou can paste this directly into AI tools or save for review.")

    copy_reflections_for_gemini = export_end_surveys

    def save_targets(self):
        for tag, entry in self.target_entries.items():
            val = entry.get().strip()
            try:
                val_f = float(val)
                if val_f > 0:
                    self.app.tag_targets[tag] = val_f
            except ValueError:
                pass
        self.app.save_data()
        messagebox.showinfo("Saved", "Hourly target goals saved successfully!")

    # --- Tab 2: Custom Tags Manager ---
    def setup_tags_tab(self, frame):
        tk.Label(frame, text="🏷️ Custom Subject Tags", font=("Segoe UI", 10, "bold"), bg="#121212", fg="#00bcd4").pack(anchor="w", pady=(10, 2), padx=10)
        tk.Label(frame, text="Create custom subject tags for tracking study time:", font=("Segoe UI", 8), bg="#121212", fg="#888888").pack(anchor="w", padx=10, pady=(0, 6))

        self.tags_listbox = tk.Listbox(frame, bg="#000000", fg="#ffffff", selectbackground="#00bcd4", selectforeground="black", highlightthickness=0, borderwidth=0, height=10, exportselection=False)
        self.tags_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        for tag in self.app.custom_tags:
            self.tags_listbox.insert(tk.END, tag)

        action_f = tk.Frame(frame, bg="#121212")
        action_f.pack(fill=tk.X, padx=10, pady=10)

        self.tag_entry = tk.Entry(action_f, bg="#1f1f1f", fg="white", insertbackground="white", font=("Segoe UI", 9), bd=0)
        self.tag_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        tk.Button(action_f, text="➕ Add Tag", bg="#4CAF50", fg="white", font=("Segoe UI", 8, "bold"), relief="flat", command=self.add_tag).pack(side=tk.LEFT, padx=2)
        tk.Button(action_f, text="🗑️ Delete Tag", bg="#f44336", fg="white", font=("Segoe UI", 8, "bold"), relief="flat", command=self.delete_tag).pack(side=tk.LEFT, padx=2)

    def add_tag(self):
        tag = self.tag_entry.get().strip()
        if tag:
            if not tag.startswith("#"):
                tag = "#" + tag
            if tag not in self.app.custom_tags:
                self.app.custom_tags.append(tag)
                self.tags_listbox.insert(tk.END, tag)
                if tag not in self.app.tag_targets:
                    self.app.tag_targets[tag] = 10.0
                self.tag_entry.delete(0, tk.END)
                self.app.update_tag_dropdown()
                self.app.save_data()

    def delete_tag(self):
        sel = self.tags_listbox.curselection()
        if sel:
            if len(self.app.custom_tags) <= 1:
                messagebox.showwarning("Warning", "You must keep at least 1 tag.")
                return
            idx = sel[0]
            tag = self.tags_listbox.get(idx)
            self.app.custom_tags.remove(tag)
            self.tags_listbox.delete(idx)
            self.app.update_tag_dropdown()
            self.app.save_data()

    # --- Tab 3: Deadlines, iCal Subscription & Completable List ---
    def setup_deadlines_tab(self, frame):
        tk.Label(frame, text="📅 iCal Calendar & Assignment Deadlines", font=("Segoe UI", 10, "bold"), bg="#121212", fg="#00bcd4").pack(anchor="w", pady=(8, 2), padx=10)
        
        # iCal Subscription URL Row
        url_card = tk.Frame(frame, bg="#1a1a1a")
        url_card.pack(fill=tk.X, padx=10, pady=4)

        tk.Label(url_card, text="iCal URL (webcal:// or https://):", font=("Segoe UI", 8, "bold"), bg="#1a1a1a", fg="#ffffff").pack(anchor="w", padx=8, pady=(4, 2))
        
        url_row = tk.Frame(url_card, bg="#1a1a1a")
        url_row.pack(fill=tk.X, padx=8, pady=(0, 6))

        self.url_entry = tk.Entry(url_row, bg="#262626", fg="white", insertbackground="white", font=("Segoe UI", 8), bd=0)
        self.url_entry.insert(0, self.app.ical_subscription_url)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        tk.Button(url_row, text="🔄 Sync URL", font=("Segoe UI", 8, "bold"), bg="#00bcd4", fg="black", relief="flat", command=self.sync_url_dialog).pack(side=tk.LEFT, padx=2)

        # File Import & Clear Row
        btn_bar = tk.Frame(frame, bg="#121212")
        btn_bar.pack(fill=tk.X, padx=10, pady=2)

        tk.Button(btn_bar, text="📂 Import .ics File", font=("Segoe UI", 8), bg="#333333", fg="white", relief="flat", command=self.import_ics_dialog).pack(side=tk.LEFT)
        tk.Button(btn_bar, text="Clear All", font=("Segoe UI", 8), bg="#333333", fg="#f44336", relief="flat", command=self.clear_deadlines).pack(side=tk.RIGHT)

        # Windows Startup Toggle
        self.startup_var = tk.BooleanVar(value=self.app.startup_check_enabled)
        cb = tk.Checkbutton(frame, text="Run on PC Startup to Check Upcoming Deadlines (< 7 Days)", variable=self.startup_var, font=("Segoe UI", 8, "bold"), bg="#121212", fg="#ff9800", selectcolor="#000000", activebackground="#121212", activeforeground="#ff9800", command=self.toggle_startup)
        cb.pack(anchor="w", padx=10, pady=2)

        # List header with Hide Attendance Checkbutton
        lbl_bar = tk.Frame(frame, bg="#121212")
        lbl_bar.pack(fill=tk.X, padx=10, pady=(4, 2))
        tk.Label(lbl_bar, text="Assignment Deadlines (Mark Done or Remove):", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#aaaaaa").pack(side=tk.LEFT)
        self.hide_attendance_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            lbl_bar,
            text="Hide Attendance",
            variable=self.hide_attendance_var,
            font=("Segoe UI", 8),
            bg="#121212",
            fg="#9e9e9e",
            selectcolor="#000000",
            activebackground="#121212",
            activeforeground="#ffffff",
            command=self.refresh_deadlines_listbox
        ).pack(side=tk.RIGHT)

        # Deadlines Listbox with Action Controls
        list_f = tk.Frame(frame, bg="#121212")
        list_f.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))

        self.deadlines_box = tk.Listbox(list_f, bg="#000000", fg="#ffffff", selectbackground="#00bcd4", selectforeground="black", highlightthickness=0, borderwidth=0, exportselection=False)
        self.deadlines_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(list_f, command=self.deadlines_box.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.deadlines_box.config(yscrollcommand=sb.set)
        self.deadlines_box.bind("<<ListboxSelect>>", self.on_deadline_selected)

        self.selected_deadline_idx = None
        self.refresh_deadlines_listbox()

        # Category Tag Assignment Bar for selected deadline
        tag_bar = tk.Frame(frame, bg="#1a1a1a", highlightbackground="#2a2a2a", highlightthickness=1)
        tag_bar.pack(fill=tk.X, padx=10, pady=(2, 4))

        tk.Label(tag_bar, text="Course Tag:", font=("Segoe UI", 8, "bold"), bg="#1a1a1a", fg="#00bcd4").pack(side=tk.LEFT, padx=(8, 4), pady=4)
        self.dl_tag_combo = ttk.Combobox(
            tag_bar,
            values=["-- None --"] + self.app.custom_tags,
            postcommand=lambda: self.dl_tag_combo.config(values=["-- None --"] + self.app.custom_tags),
            width=24,
            state="readonly",
            font=("Segoe UI", 8)
        )
        self.dl_tag_combo.set("-- None --")
        self.dl_tag_combo.pack(side=tk.LEFT, padx=4, pady=4)
        self.dl_tag_combo.bind("<<ComboboxSelected>>", self.on_tag_combo_changed)

        tk.Button(tag_bar, text="🏷️ Set Category", font=("Segoe UI", 8, "bold"), bg="#00bcd4", fg="black", relief="flat", padx=8, pady=1, command=lambda: self.assign_tag_to_selected(silent=False)).pack(side=tk.LEFT, padx=4, pady=4)

        # Action bar for selected deadline
        dl_action_bar = tk.Frame(frame, bg="#121212")
        dl_action_bar.pack(fill=tk.X, padx=10, pady=(4, 2))

        tk.Button(dl_action_bar, text="✓ Toggle Done", font=("Segoe UI", 8, "bold"), bg="#4CAF50", fg="white", relief="flat", command=self.toggle_deadline_complete).pack(side=tk.LEFT, padx=2)
        tk.Button(dl_action_bar, text="🗑️ Remove", font=("Segoe UI", 8, "bold"), bg="#f44336", fg="white", relief="flat", command=self.remove_selected_deadline).pack(side=tk.LEFT, padx=2)
        tk.Button(dl_action_bar, text="🔔 Preview Alert", font=("Segoe UI", 8), bg="#1f1f1f", fg="#ff9800", relief="flat", command=self.preview_upcoming_alert).pack(side=tk.RIGHT, padx=2)

        # Batch actions for all events with same name
        dl_batch_bar = tk.Frame(frame, bg="#121212")
        dl_batch_bar.pack(fill=tk.X, padx=10, pady=(2, 4))
        tk.Label(dl_batch_bar, text="Same Name:", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#888888").pack(side=tk.LEFT, padx=(2, 4))
        tk.Button(dl_batch_bar, text="✓ Mark All Same Done", font=("Segoe UI", 8, "bold"), bg="#2e7d32", fg="white", relief="flat", command=self.mark_all_same_completed).pack(side=tk.LEFT, padx=2)
        tk.Button(dl_batch_bar, text="📅 Mark All as Attendance", font=("Segoe UI", 8, "bold"), bg="#3949ab", fg="white", relief="flat", command=self.mark_all_same_attendance).pack(side=tk.LEFT, padx=2)


    def get_displayed_deadlines(self):
        hide_att = getattr(self, 'hide_attendance_var', None) and self.hide_attendance_var.get()
        items = self.app.deadlines
        if hide_att:
            items = [d for d in items if not d.get("is_attendance", False)]
        return sorted(items, key=lambda x: (x.get("completed", False), x.get("is_attendance", False), x["due"]))

    def on_deadline_selected(self, event=None):
        sel = self.deadlines_box.curselection()
        if sel:
            idx = sel[0]
            self.selected_deadline_idx = idx
            displayed = self.get_displayed_deadlines()
            if idx < len(displayed):
                target = displayed[idx]
                tag = target.get("tag", "")
                if tag in self.app.custom_tags:
                    self.dl_tag_combo.set(tag)
                else:
                    self.dl_tag_combo.set("-- None --")

    def on_tag_combo_changed(self, event=None):
        sel = self.deadlines_box.curselection()
        if sel or (hasattr(self, 'selected_deadline_idx') and self.selected_deadline_idx is not None):
            self.assign_tag_to_selected(silent=True)

    def assign_tag_to_selected(self, silent=False):
        sel = self.deadlines_box.curselection()
        idx = None
        if sel:
            idx = sel[0]
        elif hasattr(self, 'selected_deadline_idx') and self.selected_deadline_idx is not None:
            idx = self.selected_deadline_idx

        if idx is None:
            if not silent:
                messagebox.showwarning("Select Deadline", "Please select a deadline from the list above first.")
            return

        displayed = self.get_displayed_deadlines()
        if 0 <= idx < len(displayed):
            target = displayed[idx]
            chosen = self.dl_tag_combo.get().strip()
            if chosen == "-- None --" or not chosen:
                target.pop("tag", None)
            else:
                target["tag"] = chosen
            self.app.save_data()
            self.selected_deadline_idx = idx
            self.refresh_deadlines_listbox()
            self.deadlines_box.selection_set(idx)
            self.deadlines_box.activate(idx)
            self.deadlines_box.see(idx)
            if hasattr(self.app, 'update_imminent_deadline_banner'):
                self.app.update_imminent_deadline_banner()
            if not silent:
                tag_label = chosen if chosen and chosen != "-- None --" else "None"
                messagebox.showinfo("Category Saved! 🏷️", f"Assigned category: {tag_label}\n\nTask: {target['summary']}")


    def sync_url_dialog(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("URL Required", "Please enter an iCal or webcal subscription URL.")
            return

        self.app.ical_subscription_url = url
        self.app.save_data()
        
        try:
            content = fetch_ical_from_url(url)
            events = parse_ics_content(content)
            if not events:
                messagebox.showwarning("Empty", "No calendar events found at this URL.")
                return

            merged, added, updated = merge_calendar_events(self.app.deadlines, events)
            self.app.deadlines = merged
            self.app.save_data()
            self.refresh_deadlines_listbox()
            if hasattr(self.app, 'update_imminent_deadline_banner'):
                self.app.update_imminent_deadline_banner()
            msg = "Successfully synced calendar!\n"
            if added:
                msg += f"• Added {added} new event(s)\n"
            if updated:
                msg += f"• Updated {updated} rescheduled deadline(s)\n"
            if not added and not updated:
                msg += "All deadlines are up to date."
            messagebox.showinfo("Calendar Synced! 🔄", msg.strip())
        except Exception as ex:
            messagebox.showerror("Sync Failed", f"Could not sync calendar from URL: {ex}")


    def refresh_deadlines_listbox(self):
        self.deadlines_box.delete(0, tk.END)
        today = datetime.now().date()
        for d in self.get_displayed_deadlines():
            due_d = datetime.strptime(d["due"], "%Y-%m-%d").date()
            diff = (due_d - today).days
            
            if d.get("completed", False):
                status = "[✓ COMPLETED]"
            elif d.get("is_attendance", False):
                status = f"[📅 ATTENDANCE • {diff}d]"
            elif diff < 0: 
                status = f"[Overdue {abs(diff)}d]"
            elif diff == 0: 
                status = "[DUE TODAY]"
            elif diff == 1: 
                status = "[Tomorrow]"
            else: 
                status = f"[{diff} days left]"
            tag_badge = f"[{d['tag']}] " if d.get("tag") else "[No Tag] "
            self.deadlines_box.insert(tk.END, f"{d['due']} - {tag_badge}{d['summary']} {status}")

    def toggle_deadline_complete(self):
        sel = self.deadlines_box.curselection()
        idx = None
        if sel:
            idx = sel[0]
        elif hasattr(self, 'selected_deadline_idx') and self.selected_deadline_idx is not None:
            idx = self.selected_deadline_idx
        if idx is not None:
            displayed = self.get_displayed_deadlines()
            if 0 <= idx < len(displayed):
                target = displayed[idx]
                target["completed"] = not target.get("completed", False)
                self.app.save_data()
                self.refresh_deadlines_listbox()
                new_displayed = self.get_displayed_deadlines()
                try:
                    new_idx = new_displayed.index(target)
                    self.selected_deadline_idx = new_idx
                    self.deadlines_box.selection_set(new_idx)
                    self.deadlines_box.activate(new_idx)
                    self.deadlines_box.see(new_idx)
                except ValueError:
                    pass
                if hasattr(self.app, 'update_imminent_deadline_banner'):
                    self.app.update_imminent_deadline_banner()

    def mark_all_same_completed(self):
        sel = self.deadlines_box.curselection()
        idx = sel[0] if sel else getattr(self, 'selected_deadline_idx', None)
        if idx is None:
            messagebox.showwarning("Select Item", "Please select a task from the list first to mark all matching items.")
            return
        displayed = self.get_displayed_deadlines()
        if 0 <= idx < len(displayed):
            target = displayed[idx]
            target_name = target.get("summary", "").strip()
            matching = [d for d in self.app.deadlines if d.get("summary", "").strip().lower() == target_name.lower()]
            if not matching:
                return
            all_done = all(d.get("completed", False) for d in matching)
            new_state = not all_done
            state_label = "completed" if new_state else "incomplete"
            for d in matching:
                d["completed"] = new_state
            self.app.save_data()
            self.refresh_deadlines_listbox()
            if hasattr(self.app, 'update_imminent_deadline_banner'):
                self.app.update_imminent_deadline_banner()
            messagebox.showinfo("Updated! ✓", f"Marked all {len(matching)} '{target_name}' items as {state_label}!")

    def mark_all_same_attendance(self):
        sel = self.deadlines_box.curselection()
        idx = sel[0] if sel else getattr(self, 'selected_deadline_idx', None)
        if idx is None:
            messagebox.showwarning("Select Item", "Please select a task from the list first to set attendance status.")
            return
        displayed = self.get_displayed_deadlines()
        if 0 <= idx < len(displayed):
            target = displayed[idx]
            target_name = target.get("summary", "").strip()
            matching = [d for d in self.app.deadlines if d.get("summary", "").strip().lower() == target_name.lower()]
            if not matching:
                return
            all_att = all(d.get("is_attendance", False) for d in matching)
            new_state = not all_att
            for d in matching:
                d["is_attendance"] = new_state
            self.app.save_data()
            self.refresh_deadlines_listbox()
            if hasattr(self.app, 'update_imminent_deadline_banner'):
                self.app.update_imminent_deadline_banner()
            action_str = "marked as Attendance (hidden from deadline alerts & countdowns)" if new_state else "unmarked as Attendance (will show in deadline alerts)"
            messagebox.showinfo("Attendance Updated! 📅", f"All {len(matching)} '{target_name}' items {action_str}!")

    def remove_selected_deadline(self):
        sel = self.deadlines_box.curselection()
        idx = None
        if sel:
            idx = sel[0]
        elif hasattr(self, 'selected_deadline_idx') and self.selected_deadline_idx is not None:
            idx = self.selected_deadline_idx
        if idx is not None:
            displayed = self.get_displayed_deadlines()
            if 0 <= idx < len(displayed):
                target = displayed[idx]
                self.app.deadlines.remove(target)
                self.app.save_data()
                self.selected_deadline_idx = None
                self.refresh_deadlines_listbox()
                if hasattr(self.app, 'update_imminent_deadline_banner'):
                    self.app.update_imminent_deadline_banner()


    def import_ics_dialog(self):
        path = filedialog.askopenfilename(title="Select iCal / .ics File", filetypes=[("iCalendar Files", "*.ics"), ("All Files", "*.*")])
        if path:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                events = parse_ics_content(content)
                if not events:
                    messagebox.showwarning("Empty Calendar", "No valid event deadlines found in this file.")
                    return

                merged, added_count, updated_count = merge_calendar_events(self.app.deadlines, events)
                self.app.deadlines = merged
                self.app.save_data()
                self.refresh_deadlines_listbox()
                if hasattr(self.app, 'update_imminent_deadline_banner'):
                    self.app.update_imminent_deadline_banner()
                msg = "Successfully imported calendar!\n"
                if added_count:
                    msg += f"• Added {added_count} new deadline(s)\n"
                if updated_count:
                    msg += f"• Updated {updated_count} rescheduled deadline(s)\n"
                if not added_count and not updated_count:
                    msg += "All deadlines are up to date."
                messagebox.showinfo("Success", msg.strip())
            except Exception as ex:
                messagebox.showerror("Error", f"Failed to parse calendar file: {ex}")


    def clear_deadlines(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all imported deadlines?"):
            self.app.deadlines.clear()
            self.app.save_data()
            self.refresh_deadlines_listbox()

    def toggle_startup(self):
        enabled = self.startup_var.get()
        self.app.startup_check_enabled = enabled
        set_windows_startup(enabled)
        self.app.save_data()

    def preview_upcoming_alert(self):
        upcoming = self.app.get_deadlines_within_week()
        if upcoming:
            UpcomingDeadlinesWindow(self, upcoming, app=self.app)
        else:
            messagebox.showinfo("No Deadlines", "No pending deadlines are due within the next 7 days!")

    # --- Tab 4: Dynamic Rewards ---
    def setup_rewards_tab(self, frame):
        tk.Label(frame, text="Customize Rank Tiers & Reward Steps:", font=("Segoe UI", 9, "bold"), bg="#121212", fg="#ffffff").pack(anchor="w", pady=(10, 2), padx=10)
        tk.Label(frame, text="⚠️ Saving changes resets your reward progress to your last completed reward step.", font=("Segoe UI", 7, "italic"), bg="#121212", fg="#ff9800").pack(anchor="w", padx=10, pady=(0, 5))

        self.tiers_frame = tk.Frame(frame, bg="#121212")
        self.tiers_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        self.tier_rows_data = [dict(t) for t in self.app.rank_tiers]
        self.render_reward_rows()

        btn_bar = tk.Frame(frame, bg="#121212")
        btn_bar.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(btn_bar, text="➕ Add Reward Tier", bg="#1f1f1f", fg="#00bcd4", font=("Segoe UI", 8, "bold"), relief="flat", command=self.add_reward_row).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_bar, text="💾 Save Rewards", bg="#00bcd4", fg="black", font=("Segoe UI", 9, "bold"), relief="flat", command=self.save_rewards).pack(side=tk.RIGHT, padx=5)

    def render_reward_rows(self):
        for widget in self.tiers_frame.winfo_children():
            widget.destroy()

        self.tier_inputs = []
        for i, rank in enumerate(self.tier_rows_data):
            rf = tk.Frame(self.tiers_frame, bg="#1a1a1a", bd=1, relief="solid")
            rf.pack(fill=tk.X, pady=3)

            e_name = tk.Entry(rf, bg="#262626", fg="white", insertbackground="white", font=("Segoe UI", 8, "bold"), width=12, bd=0)
            e_name.insert(0, rank.get('name', 'Rank'))
            e_name.pack(side=tk.LEFT, padx=4, pady=4)

            e_thresh = tk.Entry(rf, bg="#262626", fg="#00bcd4", insertbackground="white", font=("Segoe UI", 8, "bold"), width=6, justify="center", bd=0)
            e_thresh.insert(0, str(rank.get('threshold', 100)))
            e_thresh.pack(side=tk.LEFT, padx=2, pady=4)
            tk.Label(rf, text="m", font=("Segoe UI", 8), bg="#1a1a1a", fg="#888888").pack(side=tk.LEFT, padx=(0, 4))

            e_reward = tk.Entry(rf, bg="#262626", fg="white", insertbackground="white", font=("Segoe UI", 8), bd=0)
            e_reward.insert(0, rank.get('reward', ''))
            e_reward.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)

            del_btn = tk.Button(rf, text="🗑️", bg="#1a1a1a", fg="#f44336", font=("Segoe UI", 8), relief="flat", activebackground="#f44336", activeforeground="white", command=lambda idx=i: self.delete_reward_row(idx))
            del_btn.pack(side=tk.RIGHT, padx=4)

            self.tier_inputs.append((e_name, e_thresh, e_reward))

    def add_reward_row(self):
        last_thresh = self.tier_rows_data[-1]["threshold"] + 100 if self.tier_rows_data else 100
        self.tier_rows_data.append({
            "name": f"Rank {len(self.tier_rows_data) + 1}",
            "threshold": last_thresh,
            "reward": "New Reward"
        })
        self.render_reward_rows()

    def delete_reward_row(self, idx):
        if len(self.tier_rows_data) <= 1:
            messagebox.showwarning("Warning", "You must keep at least 1 reward tier.")
            return
        del self.tier_rows_data[idx]
        self.render_reward_rows()

    def save_rewards(self):
        new_tiers = []
        for e_name, e_thresh, e_reward in self.tier_inputs:
            name = e_name.get().strip() or "Rank"
            thresh_str = e_thresh.get().strip()
            reward = e_reward.get().strip() or "Reward Goal"

            if not thresh_str.isdigit() or int(thresh_str) <= 0:
                messagebox.showerror("Error", f"Threshold for '{name}' must be a positive integer.")
                return
            new_tiers.append({
                "name": name,
                "threshold": int(thresh_str),
                "reward": reward
            })

        self.app.apply_reward_tier_changes(new_tiers)
        messagebox.showinfo("Saved", f"Reward tiers updated!\nYour reward progress has been adjusted to your last completed step.")

    # --- Tab 5: Badges ---
    def setup_badges_tab(self, frame):
        tk.Label(frame, text="🏆 Achievement Badges", font=("Segoe UI", 10, "bold"), bg="#121212", fg="#00bcd4").pack(anchor="w", pady=(10, 5), padx=10)
        
        unlocked = set(self.app.unlocked_badges)
        for badge in ACHIEVEMENT_DEFINITIONS:
            is_unlocked = badge["id"] in unlocked
            bf = tk.Frame(frame, bg="#1a1a1a" if is_unlocked else "#141414", highlightbackground="#00bcd4" if is_unlocked else "#222222", highlightthickness=1)
            bf.pack(fill=tk.X, padx=10, pady=4)
            
            icon_lbl = tk.Label(bf, text=badge["icon"], font=("Segoe UI", 16), bg=bf["bg"])
            icon_lbl.pack(side=tk.LEFT, padx=8, pady=4)
            
            info_f = tk.Frame(bf, bg=bf["bg"])
            info_f.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)
            
            name_color = "#ffffff" if is_unlocked else "#666666"
            desc_color = "#00bcd4" if is_unlocked else "#444444"
            status_txt = " (Unlocked)" if is_unlocked else " (Locked)"
            
            tk.Label(info_f, text=badge["name"] + status_txt, font=("Segoe UI", 9, "bold"), bg=bf["bg"], fg=name_color).pack(anchor="w")
            tk.Label(info_f, text=badge["desc"], font=("Segoe UI", 8), bg=bf["bg"], fg=desc_color).pack(anchor="w")

    # --- Tab 6: Blocker (Websites & Apps) ---
    def setup_blocker_tab(self, frame):
        tk.Label(frame, text="Distraction Blocker Configuration:", font=("Segoe UI", 9, "bold"), bg="#121212", fg="#ffffff").pack(anchor="w", pady=(8, 4), padx=10)

        tk.Label(frame, text="Blocked Websites:", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#00bcd4").pack(anchor="w", padx=10)
        self.web_listbox = tk.Listbox(frame, bg="#000000", fg="#ffffff", selectbackground="#00bcd4", selectforeground="black", highlightthickness=0, borderwidth=0, height=5, exportselection=False)
        self.web_listbox.pack(fill=tk.X, padx=10, pady=2)
        for s in self.app.blocked_websites: self.web_listbox.insert(tk.END, s)

        web_bar = tk.Frame(frame, bg="#121212")
        web_bar.pack(fill=tk.X, padx=10, pady=2)
        self.web_entry = tk.Entry(web_bar, bg="#1f1f1f", fg="#ffffff", insertbackground="white", font=("Segoe UI", 8), bd=0)
        self.web_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Button(web_bar, text="Add", bg="#4CAF50", fg="white", font=("Segoe UI", 7, "bold"), relief="flat", command=self.add_website).pack(side=tk.LEFT, padx=2)
        tk.Button(web_bar, text="Remove", bg="#f44336", fg="white", font=("Segoe UI", 7, "bold"), relief="flat", command=self.remove_website).pack(side=tk.LEFT, padx=2)

        tk.Label(frame, text="Blocked Apps (.exe):", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#00bcd4").pack(anchor="w", padx=10, pady=(6, 0))
        self.app_listbox = tk.Listbox(frame, bg="#000000", fg="#ffffff", selectbackground="#00bcd4", selectforeground="black", highlightthickness=0, borderwidth=0, height=5, exportselection=False)
        self.app_listbox.pack(fill=tk.X, padx=10, pady=2)
        for a in self.app.blocked_apps: self.app_listbox.insert(tk.END, a)

        app_bar = tk.Frame(frame, bg="#121212")
        app_bar.pack(fill=tk.X, padx=10, pady=2)
        self.app_entry = tk.Entry(app_bar, bg="#1f1f1f", fg="#ffffff", insertbackground="white", font=("Segoe UI", 8), bd=0)
        self.app_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Button(app_bar, text="Add", bg="#4CAF50", fg="white", font=("Segoe UI", 7, "bold"), relief="flat", command=self.add_app).pack(side=tk.LEFT, padx=2)
        tk.Button(app_bar, text="Remove", bg="#f44336", fg="white", font=("Segoe UI", 7, "bold"), relief="flat", command=self.remove_app).pack(side=tk.LEFT, padx=2)

    def add_website(self):
        s = self.web_entry.get().strip().lower()
        if s and s not in self.app.blocked_websites:
            self.app.blocked_websites.append(s)
            self.web_listbox.insert(tk.END, s)
            self.web_entry.delete(0, tk.END)
            self.app.save_data()

    def remove_website(self):
        sel = self.web_listbox.curselection()
        if sel:
            idx = sel[0]
            s = self.web_listbox.get(idx)
            self.app.blocked_websites.remove(s)
            self.web_listbox.delete(idx)
            self.app.save_data()

    def add_app(self):
        a = self.app_entry.get().strip()
        if a:
            if not a.lower().endswith(".exe"): a += ".exe"
            if a not in self.app.blocked_apps:
                self.app.blocked_apps.append(a)
                self.app_listbox.insert(tk.END, a)
                self.app_entry.delete(0, tk.END)
                self.app.save_data()

    def remove_app(self):
        sel = self.app_listbox.curselection()
        if sel:
            idx = sel[0]
            a = self.app_listbox.get(idx)
            self.app.blocked_apps.remove(a)
            self.app_listbox.delete(idx)
            self.app.save_data()


# --- Main Application ---
class FocusApp:
    def __init__(self, root, is_startup_mode=False):
        self.root = root
        self.is_startup_mode = is_startup_mode
        self.root.title("Focus Timer & Study Studio")
        self.root.geometry("450x800")
        self.root.configure(bg="#000000")
        self.root.minsize(450, 800)
        self.root.maxsize(450, 800)

        # Ensure smooth Windows 11 taskbar restore and window layering
        self.root.bind("<Map>", self.on_window_map)
        self.root.after(100, self.setup_window_taskbar_style)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.youtube_permitted = False
        self.youtube_bypassed = False
        self.mode = "custom"
        self.pomo_cycle = 1 
        self.is_break = False
        self.warmup_enabled = False
        self.micro_goals = []

        # Flow Momentum Overtime & Multi-Continuation tracking
        self.is_overtime = False
        self.overtime_multiplier = 1.0
        self.continuation_count = 0
        self.chain_total_minutes = 0
        self.chain_clock_checks = 0
        self.session_chain_id = None

        # Zeigarnik Micro-commitment & Emergency Hall Pass tracking
        self.is_micro_commitment = False
        self.hall_pass_used = False
        self.is_hall_pass = False
        self.hall_pass_seconds_left = 300

        # Variables
        self.is_running = False
        self.selected_minutes = 30
        self.last_drag_angle = 90
        self.drag_float_minutes = 30.0
        self.time_left = 0
        self.peek_after_id = None

        # Data Persistence (Resolved from Application Directory)
        self.app_dir = get_app_dir()
        self.save_file = os.path.join(self.app_dir, "focus_data.json")

        data = self.load_data()
        self.total_focused_minutes = data.get("real_total_minutes", data.get("total_minutes", 90))
        self.reward_tier_minutes = data.get("reward_tier_minutes", self.total_focused_minutes)
        self.blocked_apps = data["blocked_apps"]
        self.blocked_websites = data["blocked_websites"]
        self.rank_tiers = data["ranks"]
        self.history = data["history"]
        self.streak_count = data["streak_count"]
        self.last_study_date = data["last_study_date"]
        self.unlocked_badges = data["unlocked_badges"]
        self.custom_tags = data["custom_tags"]
        self.tag_targets = data["tag_targets"]
        self.deadlines = data["deadlines"]
        self.startup_check_enabled = data["startup_check_enabled"]
        self.last_deadline_alert_date = data.get("last_deadline_alert_date", "")
        self.ical_subscription_url = data.get("ical_subscription_url", "")
        self.pre_designated_session = data.get("pre_designated_session", {"active": False, "date": "", "minutes": 45, "subject": "#Placeholder"})
        self.custom_youtube_url = data.get("custom_youtube_url", "")
        self.use_custom_youtube = data.get("use_custom_youtube", False)

        self.current_subject = self.custom_tags[0] if self.custom_tags else "#Placeholder"

        self.hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        self.redirect_ip = "127.0.0.1"

        # Check Streak Freshness with Weekend Grace Protection
        self.check_streak_update()

        # Crash Cleanup Safety Check
        self.unblock_websites()

        self.stop_phrase = "Studying is a fundamental step toward achieving my long-term goals and building a better future. Every minute I spend focused right now directly translates into knowledge, discipline, and success. I must resist temporary distractions because my education is a permanent investment in myself that no one can take away."

        # Build Pitch Black UI
        self.build_ui()

        # Update Windows startup file to ensure working directory is correct
        if self.startup_check_enabled:
            set_windows_startup(True)

        # Auto-sync iCal subscription in background if URL is configured
        if self.ical_subscription_url:
            threading.Thread(target=self.auto_sync_ical_subscription, daemon=True).start()

        # Handle Pre-Designated Session / Startup Checks
        if self.is_startup_mode:
            self.root.withdraw()
            self.root.after(200, self.handle_startup_deadline_check)
        else:
            self.root.after(400, self.check_pre_designated_session)
            self.root.after(1000, self.auto_check_upcoming_deadlines)
            self.root.after(3500, lambda: self.check_for_updates(silent=True))

    def auto_sync_ical_subscription(self):
        if not self.ical_subscription_url:
            return
        try:
            content = fetch_ical_from_url(self.ical_subscription_url)
            events = parse_ics_content(content)
            if events:
                merged, added, updated = merge_calendar_events(self.deadlines, events)
                if added > 0 or updated > 0:
                    self.deadlines = merged
                    self.save_data()
                    if hasattr(self, 'update_imminent_deadline_banner'):
                        self.root.after(0, self.update_imminent_deadline_banner)
        except Exception:
            pass

    # --- GitHub Auto-Updater ---
    def check_for_updates(self, silent=True):
        def _worker():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": "FocusFlow-Updater"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode())

                remote_tag = data.get("tag_name", "")
                remote_ver = parse_version_str(remote_tag)
                local_ver = parse_version_str(APP_VERSION)

                if remote_ver > local_ver:
                    exe_asset = None
                    for a in data.get("assets", []):
                        if a.get("name", "").lower().endswith(".exe"):
                            exe_asset = a
                            break
                    if exe_asset:
                        dl_url = exe_asset["browser_download_url"]
                        body = data.get("body", "").strip()
                        body_txt = f"\n\nRelease Notes:\n{body[:350]}" if body else ""
                        msg = f"A new version of FocusFlow ({remote_tag}) is available!{body_txt}\n\nWould you like to download and install the update now?"
                        self.root.after(0, lambda: self.prompt_download_update(remote_tag, dl_url, msg))
                    elif not silent:
                        self.root.after(0, lambda: messagebox.showinfo("Update Available", f"Version {remote_tag} is available on GitHub, but no .exe asset was found in the release."))
                elif not silent:
                    self.root.after(0, lambda: messagebox.showinfo("Up to Date ✓", f"FocusFlow is up to date (version {APP_VERSION})."))
            except Exception as ex:
                if not silent:
                    self.root.after(0, lambda: messagebox.showerror("Update Check Failed", f"Could not check for updates:\n{ex}"))

        threading.Thread(target=_worker, daemon=True).start()

    def prompt_download_update(self, tag, dl_url, msg):
        if messagebox.askyesno("Update Available 🚀", msg):
            self.download_and_apply_update(dl_url, tag)

    def download_and_apply_update(self, dl_url, tag):
        prog_win = tk.Toplevel(self.root)
        prog_win.title("Updating FocusFlow")
        prog_win.geometry("380x140")
        prog_win.configure(bg="#121212")
        prog_win.resizable(False, False)
        prog_win.transient(self.root)
        prog_win.grab_set()

        tk.Label(prog_win, text=f"Downloading FocusFlow {tag}...", font=("Segoe UI", 10, "bold"), bg="#121212", fg="#00bcd4").pack(pady=(18, 8))
        status_lbl = tk.Label(prog_win, text="Starting download...", font=("Segoe UI", 8), bg="#121212", fg="#aaaaaa")
        status_lbl.pack(pady=4)

        pbar = ttk.Progressbar(prog_win, orient="horizontal", length=320, mode="determinate")
        pbar.pack(pady=10)

        def _download_task():
            try:
                app_dir = get_app_dir()
                target_exe = sys.executable if getattr(sys, 'frozen', False) else os.path.join(app_dir, "focus_app.exe")
                temp_exe = os.path.join(app_dir, "focus_app_new.exe")

                req = urllib.request.Request(dl_url, headers={"User-Agent": "FocusFlow-Updater"})
                with urllib.request.urlopen(req, timeout=45) as response:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    chunk_size = 65536
                    with open(temp_exe, "wb") as f:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                pct = int((downloaded / total_size) * 100)
                                mb_down = downloaded / (1024 * 1024)
                                mb_tot = total_size / (1024 * 1024)
                                prog_win.after(0, lambda p=pct, d=mb_down, t=mb_tot: (
                                    pbar.config(value=p),
                                    status_lbl.config(text=f"Downloaded {d:.1f} MB of {t:.1f} MB ({p}%)")
                                ))

                prog_win.after(0, lambda: status_lbl.config(text="Installing & restarting..."))
                time.sleep(0.5)

                bat_path = os.path.join(tempfile.gettempdir(), "focus_update_swap.bat")
                bat_content = f"""@echo off
timeout /t 1 /nobreak > nul
move /y "{temp_exe}" "{target_exe}" > nul
start "" "{target_exe}"
del "%~f0"
"""
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(bat_content)

                subprocess.Popen(["cmd.exe", "/c", bat_path], shell=False, creationflags=0x08000000 if os.name == 'nt' else 0)
                self.root.after(200, lambda: (self.root.destroy(), sys.exit(0)))
            except Exception as e:
                prog_win.after(0, lambda: (prog_win.destroy(), messagebox.showerror("Update Failed", f"Failed to download update:\n{e}")))

        threading.Thread(target=_download_task, daemon=True).start()



    def on_window_map(self, event):
        if event.widget == self.root:
            try:
                if self.root.state() == "iconic":
                    self.root.deiconify()
                self.root.lift()
            except Exception:
                pass

    def setup_window_taskbar_style(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    # --- Pre-Designated Force-Start Session Handler ---
    def check_pre_designated_session(self):
        if not self.pre_designated_session or not self.pre_designated_session.get("active", False):
            return

        sched_date = self.pre_designated_session.get("date", "")
        today_str = datetime.now().date().strftime("%Y-%m-%d")

        # If designated date has arrived
        if sched_date and today_str >= sched_date:
            if not is_admin():
                relaunch_as_admin()
                return

            mins = self.pre_designated_session.get("minutes", 45)
            subj = self.pre_designated_session.get("subject", self.current_subject)

            self.pre_designated_session["active"] = False
            self.save_data()

            self.selected_minutes = mins
            self.current_subject = subj
            self.subj_var.set(subj)
            self.sync_minute_entry()

            # FORCE-START the session immediately!
            self.start_timer()
            messagebox.showinfo("🎯 Pre-Designated Session Enforced!", f"You committed to a {mins}m focus block for [{subj}] today.\n\nSession has started automatically — no excuses!")

    def open_pre_designate_dialog(self):
        PreDesignateWindow(self.root, self)

    def handle_startup_deadline_check(self):
        # 1. Check if pre-designated session is due today
        if self.pre_designated_session and self.pre_designated_session.get("active", False):
            sched_date = self.pre_designated_session.get("date", "")
            today_str = datetime.now().date().strftime("%Y-%m-%d")
            if sched_date and today_str >= sched_date:
                if not is_admin():
                    relaunch_as_admin()
                    return
                self.root.deiconify()
                self.check_pre_designated_session()
                return

        # 2. Otherwise check upcoming deadlines
        upcoming = self.get_deadlines_within_week()
        if upcoming:
            UpcomingDeadlinesWindow(
                self.root, 
                upcoming, 
                app=self,
                on_start_focus=self.show_main_and_focus,
                on_dismiss_callback=self.root.destroy
            )
        else:
            self.root.destroy()

    def show_main_and_focus(self):
        if not is_admin():
            relaunch_as_admin()
            return
        self.root.deiconify()
        self.set_exam_prep_and_focus()

    # --- Streak Multiplier Helper ---
    def get_streak_multiplier(self):
        if self.streak_count >= 14: return 1.20
        elif self.streak_count >= 7: return 1.15
        elif self.streak_count >= 5: return 1.10
        elif self.streak_count >= 3: return 1.05
        return 1.0

    def build_ui(self):
        if not is_admin():
            self.admin_banner = tk.Frame(self.root, bg="#ff9800", pady=3)
            self.admin_banner.pack(fill=tk.X, side=tk.TOP)
            tk.Label(self.admin_banner, text="⚠️ Non-Admin Mode (Websites won't be blocked)", font=("Segoe UI", 8, "bold"), bg="#ff9800", fg="#000000").pack(side=tk.LEFT, padx=5)
            tk.Button(self.admin_banner, text="Relaunch as Admin", font=("Segoe UI", 8, "bold"), bg="#212121", fg="#ffffff", relief="flat", command=relaunch_as_admin).pack(side=tk.RIGHT, padx=5)

        self.top_card = tk.Frame(self.root, bg="#121212", bd=0)
        self.top_card.pack(fill=tk.X, padx=15, pady=(10, 4))

        self.title_label = tk.Label(self.top_card, text="🎯 Focus Studio", font=("Segoe UI", 13, "bold"), bg="#121212", fg="#ffffff")
        self.title_label.pack(side=tk.LEFT, padx=10, pady=6)

        # Streak Badge with Multiplier
        streak_mult = self.get_streak_multiplier()
        streak_text = f"🔥 {self.streak_count}d Streak" + (f" ({streak_mult}x)" if streak_mult > 1.0 else "")
        self.streak_label = tk.Label(self.top_card, text=streak_text, font=("Segoe UI", 8, "bold"), bg="#1f1f1f", fg="#ff9800", padx=6, pady=2)
        self.streak_label.pack(side=tk.LEFT, padx=4)

        self.settings_btn = tk.Button(self.top_card, text="⚙ Stats & Settings", font=("Segoe UI", 8, "bold"), bg="#1f1f1f", fg="#ffffff", activebackground="#333333", activeforeground="white", relief="flat", padx=8, command=self.open_settings)
        self.settings_btn.pack(side=tk.RIGHT, padx=8, pady=6)

        # Next Imminent Deadline & Recommendation Banner
        self.deadline_banner = tk.Frame(self.root, bg="#14141e", highlightbackground="#ff9800", highlightthickness=1)
        self.deadline_banner.pack(fill=tk.X, padx=15, pady=(2, 4))

        self.dl_banner_top = tk.Frame(self.deadline_banner, bg="#14141e")
        self.dl_banner_top.pack(fill=tk.X, padx=8, pady=(4, 1))

        self.dl_urgency_lbl = tk.Label(self.dl_banner_top, text="", font=("Segoe UI", 8, "bold"), bg="#14141e", fg="#ff9800", anchor="w")
        self.dl_urgency_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.dl_banner_bot = tk.Frame(self.deadline_banner, bg="#14141e")
        self.dl_banner_bot.pack(fill=tk.X, padx=8, pady=(1, 4))

        self.dl_rec_lbl = tk.Label(self.dl_banner_bot, text="", font=("Segoe UI", 7, "bold"), bg="#14141e", fg="#cccccc", anchor="w")
        self.dl_rec_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.dl_banner_combo = ttk.Combobox(self.dl_banner_bot, values=["-- Choose Course --"] + self.custom_tags, width=15, state="readonly", font=("Segoe UI", 7, "bold"))
        self.dl_banner_combo.pack(side=tk.LEFT, padx=3)
        self.dl_banner_combo.bind("<<ComboboxSelected>>", self.on_banner_tag_selected)

        self.dl_action_btn = tk.Button(self.dl_banner_bot, text="🎯 Target", font=("Segoe UI", 7, "bold"), bg="#00bcd4", fg="black", relief="flat", padx=6, pady=1)
        self.dl_action_btn.pack(side=tk.RIGHT)

        # Mode, Custom Subject Tag Bar & Pre-Schedule Button
        self.mode_frame = tk.Frame(self.root, bg="#000000")
        self.mode_frame.pack(pady=2)

        self.custom_mode_btn = tk.Button(self.mode_frame, text="⏱️ Custom", font=("Segoe UI", 8, "bold"), bg="#00bcd4", fg="black", relief="flat", padx=6, command=lambda: self.switch_app_mode("custom"))
        self.custom_mode_btn.pack(side=tk.LEFT, padx=2)

        self.pomo_mode_btn = tk.Button(self.mode_frame, text="🍅 Pomodoro", font=("Segoe UI", 8, "bold"), bg="#1f1f1f", fg="#ffffff", relief="flat", padx=6, command=lambda: self.switch_app_mode("pomodoro"))
        self.pomo_mode_btn.pack(side=tk.LEFT, padx=2)

        tk.Label(self.mode_frame, text="Tag:", font=("Segoe UI", 8, "bold"), bg="#000000", fg="#888888").pack(side=tk.LEFT, padx=(6, 2))
        self.subj_var = tk.StringVar(value=self.current_subject)
        self.subj_combo = ttk.Combobox(self.mode_frame, textvariable=self.subj_var, values=self.custom_tags, width=11, state="readonly", font=("Segoe UI", 8, "bold"))
        self.subj_combo.pack(side=tk.LEFT, padx=2)
        self.subj_combo.bind("<<ComboboxSelected>>", self.on_subject_change)

        self.sched_btn = tk.Button(self.mode_frame, text="📅 Pre-Schedule", font=("Segoe UI", 8, "bold"), bg="#1f1f1f", fg="#ff9800", relief="flat", padx=6, command=self.open_pre_designate_dialog)
        self.sched_btn.pack(side=tk.LEFT, padx=3)

        self.stats_label = tk.Label(self.root, text=self.format_total_time(), font=("Segoe UI", 8, "bold"), bg="#000000", fg="#888888")
        self.stats_label.pack(pady=(2, 2))

        self.controls_frame = tk.Frame(self.root, bg="#000000")
        self.controls_frame.pack(pady=2)

        preset_frame = tk.Frame(self.controls_frame, bg="#000000")
        preset_frame.pack(pady=2)

        for mins in [15, 25, 45, 60, 90]:
            btn = tk.Button(preset_frame, text=f"{mins}m", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#00bcd4", activebackground="#00bcd4", activeforeground="black", relief="flat", width=4, command=lambda m=mins: self.set_preset_minutes(m))
            btn.pack(side=tk.LEFT, padx=2)

        tk.Button(preset_frame, text="⚡ 5m", font=("Segoe UI", 8, "bold"), bg="#1f142b", fg="#e040fb", activebackground="#e040fb", activeforeground="black", relief="flat", width=4, command=self.start_5min_micro_commitment).pack(side=tk.LEFT, padx=2)

        direct_frame = tk.Frame(self.controls_frame, bg="#000000")
        direct_frame.pack(pady=2)

        tk.Label(direct_frame, text="Timer (mins):", font=("Segoe UI", 8, "bold"), bg="#000000", fg="#cccccc").pack(side=tk.LEFT, padx=4)
        self.minute_entry = tk.Entry(direct_frame, width=5, font=("Segoe UI", 8, "bold"), bg="#121212", fg="#ffffff", insertbackground="white", justify="center", bd=0)
        self.minute_entry.pack(side=tk.LEFT, padx=2)
        self.minute_entry.bind("<KeyRelease>", self.on_minute_entry_change)

        self.warmup_var = tk.BooleanVar(value=False)
        self.warmup_cb = tk.Checkbutton(self.controls_frame, text="🧘 1-Min Mindfulness Warm-Up", variable=self.warmup_var, font=("Segoe UI", 8, "bold"), bg="#000000", fg="#ab47bc", selectcolor="#121212", activebackground="#000000", activeforeground="#ab47bc")
        self.warmup_cb.pack(pady=2)

        self.canvas = tk.Canvas(self.root, width=170, height=170, bg="#000000", highlightthickness=0, cursor="hand2")
        self.canvas.pack(pady=2)
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.on_drag)

        self.goals_card = tk.Frame(self.root, bg="#121212", bd=0)
        self.goals_card.pack(fill=tk.X, padx=15, pady=3)

        tk.Label(self.goals_card, text="📋 Session Micro-Goals", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#00bcd4").pack(anchor="w", padx=10, pady=(4, 2))

        g_input_frame = tk.Frame(self.goals_card, bg="#121212")
        g_input_frame.pack(fill=tk.X, padx=10, pady=2)

        self.goal_entry = tk.Entry(g_input_frame, bg="#1f1f1f", fg="white", insertbackground="white", font=("Segoe UI", 8), bd=0)
        self.goal_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.goal_entry.bind("<Return>", lambda e: self.add_micro_goal())

        tk.Button(g_input_frame, text="+ Goal", font=("Segoe UI", 7, "bold"), bg="#00bcd4", fg="black", relief="flat", command=self.add_micro_goal).pack(side=tk.RIGHT)

        self.goals_list_frame = tk.Frame(self.goals_card, bg="#121212")
        self.goals_list_frame.pack(fill=tk.X, padx=10, pady=(2, 4))

        self.audio_card = tk.Frame(self.root, bg="#121212", bd=0)
        self.audio_card.pack(fill=tk.X, padx=15, pady=3)

        # Active Boost Badge Label
        self.boost_badge_lbl = tk.Label(self.audio_card, text="", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#ff9800")
        self.boost_badge_lbl.pack(pady=(2, 0))

        launch_row = tk.Frame(self.audio_card, bg="#121212")
        launch_row.pack(fill=tk.X, padx=10, pady=4)

        self.yt_btn = tk.Button(launch_row, text="▶️ YouTube Rain", font=("Segoe UI", 8, "bold"), bg="#cc181e", fg="white", activebackground="#e62117", activeforeground="white", relief="flat", command=self.open_youtube_stream)
        self.yt_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))

        self.spot_btn = tk.Button(launch_row, text="🎧 Spotify App", font=("Segoe UI", 8, "bold"), bg="#1db954", fg="black", activebackground="#1ed760", activeforeground="black", relief="flat", command=self.launch_spotify)
        self.spot_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        # Custom YouTube Stream Row (Optional select box)
        self.custom_yt_row = tk.Frame(self.audio_card, bg="#121212")
        self.custom_yt_row.pack(fill=tk.X, padx=10, pady=(0, 4))

        self.use_custom_yt_var = tk.BooleanVar(value=self.use_custom_youtube)
        self.custom_yt_cb = tk.Checkbutton(
            self.custom_yt_row,
            text="Custom Stream:",
            variable=self.use_custom_yt_var,
            font=("Segoe UI", 7, "bold"),
            bg="#121212",
            fg="#ff9800",
            selectcolor="#000000",
            activebackground="#121212",
            activeforeground="#ff9800",
            command=self.on_toggle_custom_yt
        )
        self.custom_yt_cb.pack(side=tk.LEFT, padx=(0, 3))

        self.custom_yt_entry = tk.Entry(self.custom_yt_row, bg="#1c1c28", fg="white", insertbackground="white", font=("Segoe UI", 7), bd=0)
        self.custom_yt_entry.insert(0, self.custom_youtube_url)
        self.custom_yt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.custom_yt_entry.bind("<FocusOut>", self.save_custom_yt_url)
        self.custom_yt_entry.bind("<Return>", self.save_custom_yt_url)

        self.update_yt_btn_label()

        # Mid-Session Action Buttons Row (accessible on audio card)
        action_subrow = tk.Frame(self.audio_card, bg="#121212")
        action_subrow.pack(fill=tk.X, padx=10, pady=(0, 4))

        self.yt_bypass_btn = tk.Button(action_subrow, text="🔓 Unblock YouTube", font=("Segoe UI", 7, "bold"), bg="#1a1a1a", fg="#ff9800", relief="flat", command=self.toggle_youtube_bypass)
        self.yt_bypass_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))

        self.hall_pass_btn = tk.Button(action_subrow, text="🚽 5m Hall Pass (1)", font=("Segoe UI", 7, "bold"), bg="#1a1a1a", fg="#00bcd4", relief="flat", command=self.activate_hall_pass)
        self.hall_pass_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        self.rank_card = tk.Frame(self.root, bg="#121212")
        self.rank_card.pack(fill=tk.X, padx=15, pady=3)
        
        self.rank_label = tk.Label(self.rank_card, text="", font=("Segoe UI", 9, "bold"), bg="#121212", fg="#00bcd4")
        self.rank_label.pack(pady=(4, 1))
        
        self.prog_canvas = tk.Canvas(self.rank_card, width=380, height=10, bg="#121212", highlightthickness=0)
        self.prog_canvas.pack(pady=2)
        
        self.reward_label = tk.Label(self.rank_card, text="", font=("Segoe UI", 8), bg="#121212", fg="#aaaaaa")
        self.reward_label.pack(pady=(1, 4))

        self.start_btn = tk.Button(self.root, text="🚀 START FOCUS", font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white", activebackground="#45a049", activeforeground="white", relief="flat", width=18, pady=4, command=self.on_start_button_click)
        self.start_btn.pack(pady=4)

        self.micro_start_btn = tk.Button(self.root, text="⚡ I Can't Focus Today (Just 5 Mins)", font=("Segoe UI", 8, "bold"), bg="#141124", fg="#e040fb", activebackground="#e040fb", activeforeground="black", relief="flat", width=28, pady=2, command=self.start_5min_micro_commitment)
        self.micro_start_btn.pack(pady=(0, 4))

        self.emerge_btn = tk.Button(self.root, text="Stop", font=("Segoe UI", 7), bg="black", fg="#440000", relief="flat", borderwidth=0, highlightthickness=0, activebackground="black", activeforeground="red", cursor="hand2", command=self.trigger_stop_protocol)

        self.root.bind("<ButtonPress-1>", self.handle_window_click)

        self.sync_minute_entry()
        self.draw_clock(self.selected_minutes)
        self.update_rank_ui()
        self.update_imminent_deadline_banner()

    # --- Mid-Session YouTube Bypass Toggle ---
    def toggle_youtube_bypass(self):
        if not (self.youtube_bypassed or self.youtube_permitted):
            self.youtube_bypassed = True
            self.youtube_permitted = True
            self.unblock_websites() # Lift host block
            self.block_websites()   # Re-block excluding youtube
            self.yt_bypass_btn.config(text="🔒 Re-Block YouTube", bg="#ff9800", fg="black")
            messagebox.showinfo("YouTube Unblocked", "YouTube is now temporarily unblocked.\nClick 'Re-Block YouTube' when finished!")
        else:
            self.youtube_bypassed = False
            self.youtube_permitted = False
            self.unblock_websites()
            self.block_websites()
            self.yt_bypass_btn.config(text="🔓 Unblock YouTube", bg="#1a1a1a", fg="#ff9800")
            messagebox.showinfo("YouTube Re-Blocked", "YouTube has been completely re-blocked.")

    # --- 5-Minute Emergency Hall Pass Logic ---
    def activate_hall_pass(self):
        if not self.is_running or self.is_break or self.hall_pass_used:
            return

        self.hall_pass_used = True
        self.is_hall_pass = True
        self.hall_pass_seconds_left = 300
        if hasattr(self, 'hall_pass_btn'):
            self.hall_pass_btn.config(text="🚽 Hall Pass Used", bg="#121212", fg="#555555", state="disabled")
        self.unblock_websites()

        self.hall_pass_frame = tk.Frame(self.root, bg="#0d0d15", highlightbackground="#00bcd4", highlightthickness=2)
        self.hall_pass_frame.place(relx=0.5, rely=0.5, anchor="center", width=380, height=270)

        tk.Label(self.hall_pass_frame, text="🚽 5-Minute Emergency Hall Pass", font=("Segoe UI", 11, "bold"), bg="#0d0d15", fg="#00bcd4").pack(pady=(16, 4))
        tk.Label(self.hall_pass_frame, text="Grab water, stretch, or use the restroom.\nFocus mode will automatically resume at zero!", font=("Segoe UI", 8), bg="#0d0d15", fg="#cccccc", justify="center").pack(pady=(0, 8))

        self.hp_timer_lbl = tk.Label(self.hall_pass_frame, text="05:00", font=("Segoe UI", 28, "bold"), bg="#0d0d15", fg="#ffffff")
        self.hp_timer_lbl.pack(pady=8)

        tk.Button(self.hall_pass_frame, text="⚡ Ready Early / Resume Focus", font=("Segoe UI", 9, "bold"), bg="#4CAF50", fg="white", relief="flat", padx=10, pady=4, command=self.end_hall_pass).pack(pady=10)

        self.hall_pass_loop()

    def hall_pass_loop(self):
        if not self.is_hall_pass or not hasattr(self, 'hall_pass_frame') or not self.hall_pass_frame.winfo_exists():
            return

        if self.hall_pass_seconds_left <= 0:
            self.end_hall_pass()
            return

        m, s = divmod(self.hall_pass_seconds_left, 60)
        self.hp_timer_lbl.config(text=f"{m:02d}:{s:02d}")

        if self.hall_pass_seconds_left == 60:
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                pass
            self.hp_timer_lbl.config(fg="#ff9800")

        self.hall_pass_seconds_left -= 1
        self.root.after(1000, self.hall_pass_loop)

    def end_hall_pass(self):
        self.is_hall_pass = False
        if hasattr(self, 'hall_pass_frame') and self.hall_pass_frame.winfo_exists():
            self.hall_pass_frame.destroy()
        if self.is_running:
            self.block_websites()
            try:
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

    # --- Zeigarnik Micro-Commitment (5-Minute Low Friction Start) ---
    def start_5min_micro_commitment(self):
        if self.is_running:
            return
        if not is_admin():
            if messagebox.askyesno("Admin Mode Recommended", "Distraction Blocker requires Administrator rights to block websites & apps.\n\nRelaunch as Administrator now to enable full blocking?"):
                relaunch_as_admin()
                return
        self.is_micro_commitment = True
        self.selected_minutes = 5
        self.drag_float_minutes = 5.0
        self.draw_clock(5)
        self.sync_minute_entry()
        self.start_timer()

    # --- Imminent Deadline & Recommendation Engine ---
    def get_imminent_deadline_and_recommendation(self):
        today = datetime.now().date()
        pending = []
        for d in self.deadlines:
            if d.get("completed", False) or d.get("is_attendance", False):
                continue
            sum_lower = d.get("summary", "").lower()
            if "läsnäolo" in sum_lower or "attendance" in sum_lower:
                continue

            try:
                due_d = datetime.strptime(d["due"], "%Y-%m-%d").date()
                days_left = (due_d - today).days
                pending.append((days_left, due_d, d))
            except Exception:
                pass
        if not pending:
            return None, None, None, None

        pending.sort(key=lambda x: x[0])
        days_left, due_d, closest = pending[0]
        summary = closest.get("summary", "")

        # Only check explicitly assigned tag or exact literal tag substring in summary. Otherwise NONE.
        matched_tag = closest.get("tag")
        if matched_tag not in self.custom_tags:
            matched_tag = None
            sum_lower = summary.lower()
            for tag in self.custom_tags:
                clean_tag = tag.lstrip('#').lower()
                if len(clean_tag) >= 3 and clean_tag in sum_lower:
                    matched_tag = tag
                    break

        rec_mins = 60 if days_left <= 3 else (45 if days_left <= 7 else 30)
        return closest, days_left, matched_tag, rec_mins

    def update_imminent_deadline_banner(self):
        if not hasattr(self, 'deadline_banner'):
            return
        closest, days_left, matched_tag, rec_mins = self.get_imminent_deadline_and_recommendation()
        if not closest:
            self.deadline_banner.pack_forget()
            return

        if not self.deadline_banner.winfo_ismapped() and not self.is_running:
            self.deadline_banner.pack(after=self.top_card, fill=tk.X, padx=15, pady=(2, 4))

        sum_txt = closest['summary']
        if len(sum_txt) > 38:
            sum_txt = sum_txt[:35] + "..."

        if days_left < 0:
            urgency_txt = f"🚨 OVERDUE: {sum_txt} ({abs(days_left)}d overdue!)"
            urgency_color = "#f44336"
        elif days_left == 0:
            urgency_txt = f"🚨 DUE TODAY: {sum_txt}"
            urgency_color = "#f44336"
        elif days_left == 1:
            urgency_txt = f"🔥 DUE TOMORROW: {sum_txt}"
            urgency_color = "#ff9800"
        else:
            urgency_txt = f"⏳ NEXT UP: {sum_txt} ({days_left}d left • {closest['due']})"
            urgency_color = "#00bcd4"

        self.dl_urgency_lbl.config(text=urgency_txt, fg=urgency_color)

        # Update combobox values
        combo_vals = ["-- Choose Course --"] + self.custom_tags
        self.dl_banner_combo['values'] = combo_vals

        if matched_tag and matched_tag in self.custom_tags:
            self.dl_banner_combo.set(matched_tag)
            self.dl_rec_lbl.config(text=f"💡 Suggestion: {rec_mins}m on [{matched_tag}]")
            self.dl_action_btn.config(
                text=f"🎯 Target & {rec_mins}m",
                bg="#00bcd4",
                command=lambda t=matched_tag, m=rec_mins: self.apply_deadline_recommendation(t, m)
            )
        else:
            self.dl_banner_combo.set("-- Choose Course --")
            self.dl_rec_lbl.config(text=f"💡 Suggestion: {rec_mins}m • Assign tag:")
            self.dl_action_btn.config(
                text="🎯 Target",
                bg="#333333",
                command=lambda c=closest, m=rec_mins: self.prompt_or_apply_banner_tag(c, m)
            )

    def on_banner_tag_selected(self, event=None):
        closest, days_left, _, rec_mins = self.get_imminent_deadline_and_recommendation()
        if not closest:
            return
        chosen = self.dl_banner_combo.get()
        if chosen in self.custom_tags:
            closest["tag"] = chosen
            self.save_data()
            self.current_subject = chosen
            self.subj_var.set(chosen)
            self.update_imminent_deadline_banner()

    def prompt_or_apply_banner_tag(self, closest, rec_mins):
        chosen = self.dl_banner_combo.get()
        if not chosen or chosen not in self.custom_tags:
            messagebox.showwarning("Select Course Tag", "Please choose a course category from the dropdown first to target this assignment!")
            return
        closest["tag"] = chosen
        self.save_data()
        self.apply_deadline_recommendation(chosen, rec_mins)

    def apply_deadline_recommendation(self, tag, mins):
        if tag in self.custom_tags:
            self.current_subject = tag
            self.subj_var.set(tag)
        self.selected_minutes = mins
        self.drag_float_minutes = float(mins)
        self.draw_clock(mins)
        self.sync_minute_entry()
        messagebox.showinfo("Target Selected! 🎯", f"Target set to [{tag}] for {mins} minutes.\nClick START FOCUS whenever you're ready to crush it!")

    # --- Flow Momentum Overtime Logic ---
    def prompt_flow_momentum(self, base_minutes):
        self.root.configure(bg="#000000")
        FlowMomentumWindow(
            self.root,
            base_minutes=base_minutes,
            continuation_count=getattr(self, 'continuation_count', 0),
            chain_total_minutes=getattr(self, 'chain_total_minutes', base_minutes),
            on_select_boost=self.start_overtime_boost,
            on_finish=self.finish_chain_session
        )

    def start_overtime_boost(self, extension_minutes, multiplier):
        self.is_overtime = True
        self.overtime_multiplier = multiplier
        self.continuation_count = getattr(self, 'continuation_count', 0) + 1
        self.chain_total_minutes = getattr(self, 'chain_total_minutes', 0) + extension_minutes
        self.selected_minutes = extension_minutes
        self.time_left = extension_minutes * 60
        self.is_running = True
        self.last_peek_time = 0
        self.clock_checks = 0

        self.block_websites()

        if hasattr(self, 'boost_badge_lbl'):
            c_tag = f"Continue #{self.continuation_count}"
            if self.continuation_count == 2: c_tag = "Double Continue"
            elif self.continuation_count == 3: c_tag = "Triple Continue"
            self.boost_badge_lbl.config(text=f"🔥 {multiplier}x Boost Active (+{extension_minutes}m • {c_tag} • {self.chain_total_minutes}m total)")

        self.root.configure(bg="#000000")
        self.canvas.configure(bg="#000000")
        self.audio_card.configure(bg="#000000")
        
        self.audio_card.pack(fill=tk.X, padx=15, pady=(20, 10))
        self.emerge_btn.place(x=405, y=750, width=35, height=20)
        self.update_loop()

    def finish_chain_session(self):
        total_mins = getattr(self, 'chain_total_minutes', self.selected_minutes)
        c_count = getattr(self, 'continuation_count', 0)
        c_checks = getattr(self, 'chain_clock_checks', getattr(self, 'clock_checks', 0))
        subj = self.current_subject

        self.is_overtime = False
        self.overtime_multiplier = 1.0
        self.is_running = False
        self.continuation_count = 0
        self.chain_total_minutes = 0
        self.chain_clock_checks = 0

        self.reset_to_setup_view()
        self.prompt_post_session_reflection(
            minutes=total_mins,
            subject=subj,
            continuation_count=c_count,
            clock_checks=c_checks
        )

    finish_regular_session = finish_chain_session

    def prompt_post_session_reflection(self, minutes, subject=None, continuation_count=0, clock_checks=None):
        info = {
            "minutes": minutes,
            "subject": subject or self.current_subject,
            "clock_checks": clock_checks if clock_checks is not None else getattr(self, 'clock_checks', 0),
            "continuation_count": continuation_count
        }
        self.root.after(250, lambda: PostSessionReflectionWindow(
            self.root,
            info,
            on_save_callback=self.save_post_session_reflection
        ))

    def save_post_session_reflection(self, reflection):
        if self.history:
            self.history[-1]["reflection"] = reflection
            self.save_data()

    # --- Deadline Checks & Auto-Alert ---
    def get_deadlines_within_week(self):
        today = datetime.now().date()
        upcoming = []
        for d in self.deadlines:
            if d.get("completed", False) or d.get("is_attendance", False):
                continue
            sum_lower = d.get("summary", "").lower()
            if "läsnäolo" in sum_lower or "attendance" in sum_lower:
                continue

            try:
                due_d = datetime.strptime(d["due"], "%Y-%m-%d").date()
                days_left = (due_d - today).days
                if days_left <= 7:
                    upcoming.append(d)
            except Exception:
                pass
        return sorted(upcoming, key=lambda x: x["due"])

    def auto_check_upcoming_deadlines(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        if self.last_deadline_alert_date == today_str:
            return
        
        upcoming = self.get_deadlines_within_week()
        if upcoming:
            self.last_deadline_alert_date = today_str
            self.save_data()
            UpcomingDeadlinesWindow(self.root, upcoming, app=self, on_start_focus=self.set_exam_prep_and_focus)

    def set_exam_prep_and_focus(self):
        closest, _, matched_tag, rec_mins = self.get_imminent_deadline_and_recommendation()
        if matched_tag and matched_tag in self.custom_tags:
            self.subj_var.set(matched_tag)
            self.current_subject = matched_tag
            if rec_mins:
                self.selected_minutes = rec_mins
                self.drag_float_minutes = float(rec_mins)
                self.draw_clock(rec_mins)
                self.sync_minute_entry()
        elif self.current_subject in self.custom_tags:
            self.subj_var.set(self.current_subject)
        elif self.custom_tags:
            self.subj_var.set(self.custom_tags[0])
            self.current_subject = self.custom_tags[0]

    def update_tag_dropdown(self):
        if hasattr(self, 'subj_combo'):
            self.subj_combo['values'] = self.custom_tags
            if self.current_subject not in self.custom_tags and self.custom_tags:
                self.current_subject = self.custom_tags[0]
                self.subj_var.set(self.current_subject)

    def on_subject_change(self, event=None):
        self.current_subject = self.subj_var.get()

    def add_micro_goal(self):
        text = self.goal_entry.get().strip()
        if text and len(self.micro_goals) < 3:
            self.micro_goals.append({"task": text, "done": False})
            self.goal_entry.delete(0, tk.END)
            self.render_micro_goals()

    def render_micro_goals(self):
        for w in self.goals_list_frame.winfo_children():
            w.destroy()

        for i, g in enumerate(self.micro_goals):
            gf = tk.Frame(self.goals_list_frame, bg="#121212")
            gf.pack(fill=tk.X, pady=1)

            cb_var = tk.BooleanVar(value=g["done"])
            cb = tk.Checkbutton(gf, variable=cb_var, bg="#121212", activebackground="#121212", selectcolor="#000000", command=lambda idx=i, v=cb_var: self.toggle_goal_done(idx, v.get()))
            cb.pack(side=tk.LEFT)

            txt_fg = "#888888" if g["done"] else "#ffffff"
            tk.Label(gf, text=g["task"], font=("Segoe UI", 8), bg="#121212", fg=txt_fg).pack(side=tk.LEFT, fill=tk.X, expand=True)

            del_b = tk.Button(gf, text="×", font=("Segoe UI", 8, "bold"), bg="#121212", fg="#f44336", bd=0, relief="flat", command=lambda idx=i: self.delete_micro_goal(idx))
            del_b.pack(side=tk.RIGHT)

    def toggle_goal_done(self, idx, is_done):
        if idx < len(self.micro_goals):
            self.micro_goals[idx]["done"] = is_done
            self.render_micro_goals()

    def delete_micro_goal(self, idx):
        if idx < len(self.micro_goals):
            del self.micro_goals[idx]
            self.render_micro_goals()

    # --- Mindfulness Warm-Up Overlay ---
    def on_start_button_click(self):
        self.is_overtime = False
        self.overtime_multiplier = 1.0
        if not is_admin():
            if messagebox.askyesno("Admin Mode Recommended", "Distraction Blocker requires Administrator rights to block websites & apps.\n\nRelaunch as Administrator now to enable full blocking?"):
                relaunch_as_admin()
                return
        if self.warmup_var.get():
            self.start_mindfulness_warmup()
        else:
            self.start_timer()

    def start_mindfulness_warmup(self):
        self.warmup_seconds = 60
        self.warmup_frame = tk.Frame(self.root, bg="#0d0d15")
        self.warmup_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        tk.Label(self.warmup_frame, text="🧘 1-Minute Mindfulness Warm-Up", font=("Segoe UI", 12, "bold"), bg="#0d0d15", fg="#ab47bc").pack(pady=(30, 5))
        self.warmup_phase_lbl = tk.Label(self.warmup_frame, text="Breathe In...", font=("Segoe UI", 10, "italic"), bg="#0d0d15", fg="#00bcd4")
        self.warmup_phase_lbl.pack(pady=5)

        self.warmup_canvas = tk.Canvas(self.warmup_frame, width=220, height=220, bg="#0d0d15", highlightthickness=0)
        self.warmup_canvas.pack(pady=10)

        self.warmup_timer_lbl = tk.Label(self.warmup_frame, text="60s", font=("Segoe UI", 10, "bold"), bg="#0d0d15", fg="#ffffff")
        self.warmup_timer_lbl.pack(pady=5)

        tk.Button(self.warmup_frame, text="Skip Warm-Up", font=("Segoe UI", 8, "bold"), bg="#313244", fg="#cdd6f4", relief="flat", command=self.skip_warmup).pack(pady=15)

        self.warmup_loop()

    def warmup_loop(self):
        if not hasattr(self, 'warmup_frame') or not self.warmup_frame.winfo_exists():
            return

        if self.warmup_seconds <= 0:
            self.skip_warmup()
            return

        sec_passed = 60 - self.warmup_seconds
        cycle_sec = sec_passed % 14
        
        if cycle_sec < 4:
            phase = "Breathe In... 🌬️"
            radius = 30 + (cycle_sec / 4.0) * 55
        elif cycle_sec < 8:
            phase = "Hold... 😌"
            radius = 85
        else:
            phase = "Breathe Out... 💨"
            radius = 85 - ((cycle_sec - 8) / 6.0) * 55

        self.warmup_phase_lbl.config(text=phase)
        self.warmup_timer_lbl.config(text=f"{self.warmup_seconds}s remaining")

        self.warmup_canvas.delete("all")
        cx, cy = 110, 110
        self.warmup_canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline="#ab47bc", width=4, fill="#1c162b")

        self.warmup_seconds -= 1
        self.root.after(1000, self.warmup_loop)

    def skip_warmup(self):
        if hasattr(self, 'warmup_frame') and self.warmup_frame.winfo_exists():
            self.warmup_frame.destroy()
        self.start_timer()

    # --- Mode Switcher ---
    def switch_app_mode(self, mode_str):
        if self.is_running: return
        self.mode = mode_str
        if self.mode == "pomodoro":
            self.custom_mode_btn.config(bg="#1f1f1f", fg="#ffffff")
            self.pomo_mode_btn.config(bg="#00bcd4", fg="black")
            self.selected_minutes = 25
            self.controls_frame.pack_forget()
        else:
            self.pomo_mode_btn.config(bg="#1f1f1f", fg="#ffffff")
            self.custom_mode_btn.config(bg="#00bcd4", fg="black")
            self.controls_frame.pack(after=self.mode_frame, pady=2)
        
        self.sync_minute_entry()
        self.draw_clock(self.selected_minutes)

    def on_toggle_custom_yt(self):
        self.use_custom_youtube = self.use_custom_yt_var.get()
        self.save_custom_yt_url()
        self.update_yt_btn_label()

    def save_custom_yt_url(self, event=None):
        url = self.custom_yt_entry.get().strip() if hasattr(self, 'custom_yt_entry') else ""
        self.custom_youtube_url = url
        self.use_custom_youtube = self.use_custom_yt_var.get() if hasattr(self, 'use_custom_yt_var') else False
        self.save_data()
        self.update_yt_btn_label()

    def update_yt_btn_label(self):
        if hasattr(self, 'yt_btn'):
            if getattr(self, 'use_custom_youtube', False) and getattr(self, 'custom_youtube_url', '').strip():
                self.yt_btn.config(text="▶️ Custom Stream", bg="#e65100")
            else:
                self.yt_btn.config(text="▶️ YouTube Rain", bg="#cc181e")

    def open_youtube_stream(self):
        self.youtube_permitted = True
        if self.is_running:
            self.unblock_websites()
            self.block_websites()
            if hasattr(self, 'yt_bypass_btn'):
                self.yt_bypass_btn.config(text="🔒 Re-Block YouTube", bg="#ff9800", fg="black")
        raw_url = self.custom_youtube_url.strip() if (self.use_custom_youtube and self.custom_youtube_url.strip()) else YOUTUBE_RAIN_STREAM_URL
        target_url = get_youtube_embed_url(raw_url)
        webbrowser.open(target_url)

    def launch_spotify(self):
        success = launch_spotify_app()
        if not success:
            messagebox.showwarning("Spotify", "Could not locate Spotify. Opening Web Player...")
            webbrowser.open("https://open.spotify.com")

    def open_settings(self):
        if not self.is_running:
            SettingsWindow(self.root, self)

    # --- Data Persistence ---
    def load_data(self):
        default_data = {
            "total_minutes": 0,
            "real_total_minutes": 0,
            "reward_tier_minutes": 0,
            "blocked_apps": DEFAULT_BLOCKED_APPS.copy(),
            "blocked_websites": DEFAULT_BLOCKED_WEBSITES.copy(),
            "ranks": DEFAULT_RANKS.copy(),
            "history": [],
            "streak_count": 0,
            "last_study_date": "",
            "unlocked_badges": [],
            "custom_tags": DEFAULT_TAGS.copy(),
            "tag_targets": DEFAULT_TARGETS.copy(),
            "deadlines": [],
            "startup_check_enabled": True,
            "last_deadline_alert_date": "",
            "ical_subscription_url": "",
            "pre_designated_session": {"active": False, "date": "", "minutes": 45, "subject": "#Placeholder"},
            "custom_youtube_url": "",
            "use_custom_youtube": False
        }
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    real_tot = data.get("real_total_minutes", data.get("total_minutes", 0))
                    default_data["total_minutes"] = real_tot
                    default_data["real_total_minutes"] = real_tot
                    default_data["reward_tier_minutes"] = data.get("reward_tier_minutes", real_tot)
                    if "blocked_apps" in data: default_data["blocked_apps"] = data["blocked_apps"]
                    if "blocked_websites" in data: default_data["blocked_websites"] = data["blocked_websites"]
                    if "ranks" in data: default_data["ranks"] = data["ranks"]
                    if "history" in data: default_data["history"] = data["history"]
                    if "streak_count" in data: default_data["streak_count"] = data["streak_count"]
                    if "last_study_date" in data: default_data["last_study_date"] = data["last_study_date"]
                    if "unlocked_badges" in data: default_data["unlocked_badges"] = data["unlocked_badges"]
                    if "custom_tags" in data: default_data["custom_tags"] = data["custom_tags"]
                    if "tag_targets" in data: default_data["tag_targets"] = data["tag_targets"]
                    if "deadlines" in data: default_data["deadlines"] = data["deadlines"]
                    if "startup_check_enabled" in data: default_data["startup_check_enabled"] = data["startup_check_enabled"]
                    if "last_deadline_alert_date" in data: default_data["last_deadline_alert_date"] = data["last_deadline_alert_date"]
                    if "ical_subscription_url" in data: default_data["ical_subscription_url"] = data["ical_subscription_url"]
                    if "pre_designated_session" in data: default_data["pre_designated_session"] = data["pre_designated_session"]
                    if "custom_youtube_url" in data: default_data["custom_youtube_url"] = data["custom_youtube_url"]
                    if "use_custom_youtube" in data: default_data["use_custom_youtube"] = data["use_custom_youtube"]
            except Exception:
                pass
        return default_data

    # --- Weekend Grace Period Streak Tracking ---
    def check_streak_update(self):
        if not self.last_study_date:
            return
        try:
            last_d = datetime.strptime(self.last_study_date, "%Y-%m-%d").date()
            today_d = datetime.now().date()
            
            # Count only missed weekdays (Mon-Fri) between last_d and today_d
            cur = last_d + timedelta(days=1)
            missed_weekdays = 0
            while cur < today_d:
                if cur.weekday() < 5: # Monday (0) through Friday (4)
                    missed_weekdays += 1
                cur += timedelta(days=1)

            if missed_weekdays >= 1:
                self.streak_count = 0
        except Exception:
            pass

    def record_completed_session(self, real_minutes, completed=True, reward_minutes=None, is_continuation=None, continuation_count=None, chain_total=None, chain_id=None):
        self.total_focused_minutes += real_minutes
        
        # Streak multiplier boost bonus
        streak_mult = self.get_streak_multiplier()

        if reward_minutes is None:
            reward_minutes = real_minutes

        # Apply streak boost to reward tier credit
        final_reward_credit = int(round(reward_minutes * streak_mult))
        self.reward_tier_minutes += final_reward_credit
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        c_count = continuation_count if continuation_count is not None else getattr(self, 'continuation_count', 0)
        c_flag = is_continuation if is_continuation is not None else (c_count > 0)
        c_total = chain_total if chain_total is not None else getattr(self, 'chain_total_minutes', real_minutes)
        c_id = chain_id if chain_id is not None else getattr(self, 'session_chain_id', str(time.time()))

        self.history.append({
            "date": today_str,
            "minutes": real_minutes,
            "timestamp": time.time(),
            "completed": completed,
            "mode": self.mode,
            "subject": self.current_subject,
            "goals": [g for g in self.micro_goals],
            "overtime_boost": self.overtime_multiplier if self.is_overtime else 1.0,
            "streak_boost": streak_mult,
            "is_continuation": c_flag,
            "continuation_count": c_count,
            "chain_total_minutes": c_total,
            "chain_id": c_id
        })
        
        if real_minutes >= 15 and completed:
            if not self.last_study_date:
                self.streak_count = 1
                self.last_study_date = today_str
            else:
                last_d = datetime.strptime(self.last_study_date, "%Y-%m-%d").date()
                today_d = datetime.now().date()
                
                # Check if consecutive day or consecutive weekday
                cur = last_d + timedelta(days=1)
                missed_weekdays = 0
                while cur < today_d:
                    if cur.weekday() < 5:
                        missed_weekdays += 1
                    cur += timedelta(days=1)

                if missed_weekdays == 0 and today_d > last_d:
                    self.streak_count += 1
                    self.last_study_date = today_str
                elif missed_weekdays >= 1:
                    self.streak_count = 1
                    self.last_study_date = today_str
        
        if hasattr(self, 'streak_label'):
            sm = self.get_streak_multiplier()
            st = f"🔥 {self.streak_count}d Streak" + (f" ({sm}x)" if sm > 1.0 else "")
            self.streak_label.config(text=st)

        self.check_achievements(real_minutes)
        self.save_data()

    def check_achievements(self, last_session_mins):
        new_unlocked = []

        def unlock(b_id):
            if b_id not in self.unlocked_badges:
                self.unlocked_badges.append(b_id)
                new_unlocked.append(b_id)

        if last_session_mins >= 15: unlock("first_step")
        if last_session_mins >= 60: unlock("deep_work")
        if self.total_focused_minutes >= 6000: unlock("centurion")
        if self.streak_count >= 5: unlock("streak_king")
        if datetime.now().hour >= 22: unlock("night_owl")

        for b_id in new_unlocked:
            b_def = next((b for b in ACHIEVEMENT_DEFINITIONS if b["id"] == b_id), None)
            if b_def:
                messagebox.showinfo("Achievement Unlocked! 🎉", f"Unlocked Badge: {b_def['icon']} {b_def['name']}\n{b_def['desc']}")

    def apply_reward_tier_changes(self, new_rank_tiers):
        new_rank_tiers.sort(key=lambda r: r["threshold"])
        current_reward_time = self.reward_tier_minutes
        completed_thresholds = [r["threshold"] for r in new_rank_tiers if r["threshold"] <= current_reward_time]
        new_reward_total = max(completed_thresholds) if completed_thresholds else 0
        
        self.rank_tiers = new_rank_tiers
        self.reward_tier_minutes = new_reward_total
        self.save_data()
        self.update_rank_ui()

    def save_data(self):
        data = {
            "total_minutes": self.total_focused_minutes,
            "real_total_minutes": self.total_focused_minutes,
            "reward_tier_minutes": self.reward_tier_minutes,
            "blocked_apps": self.blocked_apps,
            "blocked_websites": self.blocked_websites,
            "ranks": self.rank_tiers,
            "history": self.history,
            "streak_count": self.streak_count,
            "last_study_date": self.last_study_date,
            "unlocked_badges": self.unlocked_badges,
            "custom_tags": self.custom_tags,
            "tag_targets": self.tag_targets,
            "deadlines": self.deadlines,
            "startup_check_enabled": self.startup_check_enabled,
            "last_deadline_alert_date": self.last_deadline_alert_date,
            "ical_subscription_url": self.ical_subscription_url,
            "pre_designated_session": self.pre_designated_session,
            "custom_youtube_url": getattr(self, "custom_youtube_url", ""),
            "use_custom_youtube": getattr(self, "use_custom_youtube", False)
        }
        dir_name = os.path.dirname(os.path.abspath(self.save_file))
        try:
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
                json.dump(data, tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, self.save_file)
        except Exception:
            try:
                with open(self.save_file, "w", encoding="utf-8") as file:
                    json.dump(data, file, indent=2)
            except Exception:
                pass
        
        if hasattr(self, 'stats_label'):
            self.stats_label.config(text=self.format_total_time())
        self.update_rank_ui()
        if hasattr(self, 'update_imminent_deadline_banner'):
            self.update_imminent_deadline_banner()

    # --- Rank Logic (uses reward_tier_minutes) ---
    def get_rank_info(self):
        t = self.reward_tier_minutes
        for rank in self.rank_tiers:
            if t < rank["threshold"]:
                return rank["name"], rank["threshold"], f"Next Reward: {rank['reward']}"
        
        last_rank = self.rank_tiers[-1] if self.rank_tiers else {"name": "Apex Scholar", "threshold": t, "reward": "Goal Reached!"}
        return last_rank["name"], max(t, last_rank["threshold"]), f"Ultimate Reward Unlocked: {last_rank['reward']}"

    def update_rank_ui(self):
        rank_name, next_tier_mins, reward = self.get_rank_info()
        pct = min(self.reward_tier_minutes / max(1, next_tier_mins), 1.0)
        
        self.prog_canvas.delete("all")
        self.prog_canvas.create_rectangle(0, 0, 380, 10, fill="#1f1f1f", outline="")
        
        fill_width = max(1, 380 * pct)
        self.prog_canvas.create_rectangle(0, 0, fill_width, 10, fill="#00bcd4", outline="")
        
        mins_left = next_tier_mins - self.reward_tier_minutes
        if mins_left > 0:
            bar_text = f"{self.reward_tier_minutes} / {next_tier_mins} min ({mins_left} min left)"
        else:
            bar_text = f"{self.reward_tier_minutes} min"
        self.prog_canvas.create_text(190, 5, text=bar_text, font=("Segoe UI", 7, "bold"), fill="white")
        
        self.rank_label.config(text=f"Rank: {rank_name}")
        self.reward_label.config(text=reward)

    def format_total_time(self):
        hours, minutes = divmod(self.total_focused_minutes, 60)
        if hours > 0:
            return f"⚡ Total Focused Time: {hours}h {minutes}m"
        return f"⚡ Total Focused Time: {minutes} Min"

    # --- Hosts File Blocking (with Mid-Session YouTube Bypass support) ---
    def block_websites(self):
        if not is_admin() or self.is_break:
            return
        try:
            self.unblock_websites()
            with open(self.hosts_path, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
            
            lines_to_add = [MARKER_START]
            for website in self.blocked_websites:
                site = website.strip()
                if site:
                    # YouTube Bypass Check: If bypassed or permitted, skip blocking YouTube
                    if (self.youtube_permitted or self.youtube_bypassed) and ("youtube.com" in site or "youtu.be" in site):
                        continue
                    lines_to_add.append(f"{self.redirect_ip} {site}")
            lines_to_add.append(MARKER_END)
            
            block_content = "\n".join(lines_to_add) + "\n"
            
            with open(self.hosts_path, 'a', encoding='utf-8') as file:
                if content and not content.endswith('\n'):
                    file.write("\n")
                file.write(block_content)
                
            subprocess.run(["ipconfig", "/flushdns"], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass

    def unblock_websites(self):
        if not is_admin():
            return
        try:
            if not os.path.exists(self.hosts_path):
                return
            with open(self.hosts_path, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
            
            if MARKER_START in content and MARKER_END in content:
                start_idx = content.find(MARKER_START)
                end_idx = content.find(MARKER_END) + len(MARKER_END)
                new_content = content[:start_idx] + content[end_idx:]
                
                lines = new_content.splitlines()
                with open(self.hosts_path, 'w', encoding='utf-8') as file:
                    file.write("\n".join(lines) + "\n")
                    
                subprocess.run(["ipconfig", "/flushdns"], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass

    def on_closing(self):
        if self.is_running:
            self.trigger_stop_protocol()
        else:
            self.unblock_websites()
            self.root.destroy()

    # --- Preset & Direct Input Controls ---
    def set_preset_minutes(self, mins):
        if self.is_running: return
        self.selected_minutes = mins
        self.drag_float_minutes = float(mins)
        self.draw_clock(self.selected_minutes)
        self.sync_minute_entry()

    def sync_minute_entry(self):
        if hasattr(self, 'minute_entry'):
            self.minute_entry.delete(0, tk.END)
            self.minute_entry.insert(0, str(self.selected_minutes))

    def on_minute_entry_change(self, event=None):
        if self.is_running: return
        val = self.minute_entry.get().strip()
        if val.isdigit():
            mins = int(val)
            mins = max(1, min(720, mins))
            self.selected_minutes = mins
            self.drag_float_minutes = float(mins)
            self.draw_clock(self.selected_minutes)

    # --- Continuous Float Clock Drag Math ---
    def get_angle(self, event):
        dx = event.x - 85
        dy = event.y - 85
        angle = math.degrees(math.atan2(dy, dx)) + 90
        if angle < 0:
            angle += 360
        return angle

    def start_drag(self, event):
        if self.is_running: return
        self.last_drag_angle = self.get_angle(event)
        self.drag_float_minutes = float(self.selected_minutes)

    def on_drag(self, event):
        if self.is_running: return
        new_angle = self.get_angle(event)
        diff = new_angle - self.last_drag_angle
        
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360
            
        minutes_delta = (diff / 360.0) * 120.0
        self.drag_float_minutes += minutes_delta
        self.drag_float_minutes = max(1.0, min(720.0, self.drag_float_minutes))
        
        new_minutes = int(round(self.drag_float_minutes))
        if new_minutes != self.selected_minutes:
            self.selected_minutes = new_minutes
            self.draw_clock(self.selected_minutes)
            self.sync_minute_entry()
            
        self.last_drag_angle = new_angle

    # --- Clock Drawing ---
    def draw_clock(self, minutes_total, seconds_left=None):
        self.canvas.delete("all")
        self.canvas.create_oval(10, 10, 160, 160, outline="#222222", width=4)
        for i in range(12):
            angle = math.radians(i * 30 - 90)
            x1 = 85 + 60 * math.cos(angle)
            y1 = 85 + 60 * math.sin(angle)
            x2 = 85 + 70 * math.cos(angle)
            y2 = 85 + 70 * math.sin(angle)
            self.canvas.create_line(x1, y1, x2, y2, fill="#333333", width=2)
            
        if seconds_left is None: 
            visual_extent = -(min(minutes_total, 120) / 120) * 360
            color = "#00bcd4" 
            if minutes_total >= 60:
                h, m = divmod(minutes_total, 60)
                text = f"{h}h {m}m" if m > 0 else f"{h}h"
            else:
                text = f"{minutes_total} Min"
        else: 
            total_seconds = self.selected_minutes * 60
            visual_extent = -(seconds_left / total_seconds) * 360
            color = "#ff9800" if (self.is_break or self.is_overtime) else "#f44336" 
            m, s = divmod(seconds_left, 60)
            h, m = divmod(m, 60)
            if h > 0:
                text = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                text = f"{m:02d}:{s:02d}"

        if visual_extent != 0:
            self.canvas.create_arc(10, 10, 160, 160, start=90, extent=visual_extent, outline=color, width=5, style=tk.ARC)
        
        if seconds_left is None:
            angle_deg = (minutes_total % 120) / 120 * 360
            if angle_deg == 0 and minutes_total > 0: 
                angle_deg = 360
            hx = 85 + 65 * math.cos(math.radians(angle_deg - 90))
            hy = 85 + 65 * math.sin(math.radians(angle_deg - 90))
            self.canvas.create_oval(hx - 6, hy - 6, hx + 6, hy + 6, fill="#ffffff", outline="#00bcd4", width=2)
        
        self.canvas.create_text(85, 85, text=text, font=("Segoe UI", 15, "bold"), fill="white")

    # --- Active Mode Logic ---
    def start_timer(self):
        self.is_break = False
        self.youtube_bypassed = False
        self.youtube_permitted = False
        self.hall_pass_used = False
        self.is_hall_pass = False
        self.time_left = self.selected_minutes * 60
        self.is_running = True
        self.last_peek_time = 0 
        self.clock_checks = 0
        self.last_clock_check_click = 0

        # Fresh session chain initialization
        if not getattr(self, 'is_overtime', False):
            self.continuation_count = 0
            self.chain_total_minutes = self.selected_minutes
            self.session_chain_id = str(time.time())
            self.chain_clock_checks = 0
        
        self.block_websites()

        if hasattr(self, 'boost_badge_lbl'):
            if self.is_overtime:
                self.boost_badge_lbl.config(text=f"🔥 {self.overtime_multiplier}x Flow Multiplier Active")
            elif getattr(self, 'is_micro_commitment', False):
                self.boost_badge_lbl.config(text="⚡ 5-Minute Micro-Commitment (Low Friction Start)")
            else:
                self.boost_badge_lbl.config(text="")

        if hasattr(self, 'yt_bypass_btn'):
            self.yt_bypass_btn.config(text="🔓 Unblock YouTube", bg="#1a1a1a", fg="#ff9800")
        if hasattr(self, 'hall_pass_btn'):
            self.hall_pass_btn.config(text="🚽 5m Hall Pass (1)", bg="#1a1a1a", fg="#00bcd4", state="normal")

        if hasattr(self, 'admin_banner'): self.admin_banner.pack_forget()
        self.top_card.pack_forget()
        if hasattr(self, 'deadline_banner'): self.deadline_banner.pack_forget()
        self.mode_frame.pack_forget()
        self.stats_label.pack_forget()
        self.controls_frame.pack_forget()
        self.goals_card.pack_forget()
        self.rank_card.pack_forget()
        self.start_btn.pack_forget()
        if hasattr(self, 'micro_start_btn'): self.micro_start_btn.pack_forget()
        self.canvas.pack_forget() 

        self.root.configure(bg="#000000")
        self.canvas.configure(bg="#000000")
        self.audio_card.configure(bg="#000000")
        
        self.audio_card.pack(fill=tk.X, padx=15, pady=(20, 10))

        self.emerge_btn.place(x=405, y=750, width=35, height=20)
        self.update_loop()

    def start_break_mode(self, duration_mins):
        self.is_break = True
        self.selected_minutes = duration_mins
        self.time_left = duration_mins * 60
        self.unblock_websites()
        
        self.break_frame = tk.Frame(self.root, bg="#121212", highlightbackground="#ff9800", highlightthickness=2)
        self.break_frame.place(relx=0.5, rely=0.4, anchor="center", width=380, height=260)
        
        tk.Label(self.break_frame, text="☕ Break Time - Rest & Recharge!", font=("Segoe UI", 12, "bold"), bg="#121212", fg="#ff9800").pack(pady=(15, 5))
        
        tip = random.choice(WELLNESS_TIPS)
        tk.Label(self.break_frame, text=tip, font=("Segoe UI", 9, "italic"), bg="#121212", fg="#cccccc", wraplength=340).pack(pady=10)

        b_btn_frame = tk.Frame(self.break_frame, bg="#121212")
        b_btn_frame.pack(pady=15)
        
        tk.Button(b_btn_frame, text="⚡ Skip Break / Start Focus", font=("Segoe UI", 8, "bold"), bg="#4CAF50", fg="white", relief="flat", command=self.end_break_early).pack(side=tk.LEFT, padx=5)
        tk.Button(b_btn_frame, text="End Session", font=("Segoe UI", 8), bg="#555555", fg="white", relief="flat", command=self.trigger_stop_protocol).pack(side=tk.LEFT, padx=5)

    def end_break_early(self):
        if hasattr(self, 'break_frame') and self.break_frame.winfo_exists():
            self.break_frame.destroy()
        
        if self.mode == "pomodoro":
            self.pomo_cycle = (self.pomo_cycle % 4) + 1
            self.selected_minutes = 25
            self.start_timer()
        else:
            self.reset_to_setup_view()

    def handle_window_click(self, event):
        if event.widget == self.emerge_btn:
            return
        if hasattr(self, 'stop_frame') and self.stop_frame.winfo_exists():
            return
        if hasattr(self, 'break_frame') and self.break_frame.winfo_exists():
            return
        if not self.is_running:
            return

        # Ignore clicks on interactive widgets (e.g. YouTube entry, buttons, volume sliders)
        if isinstance(event.widget, (tk.Button, tk.Entry, ttk.Combobox, tk.Scale)):
            return

        now = time.time()
        # Count clock check / peek requests (debounced by 1.5s)
        if not hasattr(self, 'last_clock_check_click') or (now - self.last_clock_check_click >= 1.5):
            self.clock_checks = getattr(self, 'clock_checks', 0) + 1
            self.chain_clock_checks = getattr(self, 'chain_clock_checks', 0) + 1
            self.last_clock_check_click = now

        current_time = time.time()
        if current_time - self.last_peek_time >= 300 or self.last_peek_time == 0:
            self.show_peek()
            self.last_peek_time = current_time

    def show_peek(self):
        if self.peek_after_id:
            self.root.after_cancel(self.peek_after_id)
            self.peek_after_id = None
        self.canvas.pack(pady=100) 
        self.draw_clock(self.selected_minutes, self.time_left)
        self.peek_after_id = self.root.after(5000, self.hide_peek)

    def hide_peek(self):
        if self.peek_after_id:
            self.root.after_cancel(self.peek_after_id)
            self.peek_after_id = None
        if self.is_running:
            self.canvas.pack_forget()

    def play_finish_sound(self):
        try:
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

    def update_loop(self):
        if self.is_running and self.time_left > 0:
            # If emergency hall pass is active, pause the focus timer
            if getattr(self, 'is_hall_pass', False):
                self.root.after(1000, self.update_loop)
                return

            if self.canvas.winfo_ismapped():
                self.draw_clock(self.selected_minutes, self.time_left)

            if not self.is_break and self.time_left % 5 == 0:
                self.enforce_rules()

            self.time_left -= 1
            self.root.after(1000, self.update_loop)
            
        elif self.time_left <= 0 and self.is_running:
            self.play_finish_sound()
            
            if not self.is_break:
                base_mins = self.selected_minutes
                
                # Check for Zeigarnik 5-minute micro-commitment
                if getattr(self, 'is_micro_commitment', False):
                    self.is_micro_commitment = False
                    self.unblock_websites()
                    ans = messagebox.askyesno(
                        "🎉 5 Minutes Conquered!",
                        "You crushed the hardest barrier: STARTING!\n\n"
                        "The Zeigarnik effect is working in your favor.\n"
                        "Would you like to keep the momentum going for a full 25-minute focus session?\n\n"
                        "(Click 'Yes' to continue 25m, or 'No' to finish now)"
                    )
                    if ans:
                        self.selected_minutes = 25
                        self.drag_float_minutes = 25.0
                        self.sync_minute_entry()
                        self.start_timer()
                        return
                    else:
                        self.record_completed_session(5, completed=True, reward_minutes=5)
                        self.finish_chain_session()
                        return

                if self.is_overtime:
                    boosted_reward = int(round(base_mins * self.overtime_multiplier))
                    self.record_completed_session(
                        base_mins,
                        completed=True,
                        reward_minutes=boosted_reward,
                        is_continuation=True,
                        continuation_count=self.continuation_count,
                        chain_total=self.chain_total_minutes,
                        chain_id=self.session_chain_id
                    )

                    # Multi-continuation: allow up to 3 continuations (Continue #1, Double Continue #2, Triple Continue #3)
                    if self.continuation_count < 3:
                        self.prompt_flow_momentum(base_mins)
                    else:
                        messagebox.showinfo(
                            "🔥 Flow Chain Complete!",
                            f"Incredible focus! You completed a Triple Continued Flow Session!\n"
                            f"Total Focused: {self.chain_total_minutes}m across {self.continuation_count + 1} blocks.\n"
                            f"All reward boosts have been credited!"
                        )
                        self.finish_chain_session()
                else:
                    self.record_completed_session(
                        base_mins,
                        completed=True,
                        reward_minutes=base_mins,
                        is_continuation=False,
                        continuation_count=0,
                        chain_total=base_mins,
                        chain_id=self.session_chain_id
                    )
                    
                    if self.mode == "pomodoro":
                        break_len = 15 if self.pomo_cycle == 4 else 5
                        self.start_break_mode(break_len)
                    else:
                        if base_mins >= 15:
                            self.prompt_flow_momentum(base_mins)
                        else:
                            self.finish_chain_session()
            else:
                if hasattr(self, 'break_frame') and self.break_frame.winfo_exists():
                    self.break_frame.destroy()
                
                if self.mode == "pomodoro":
                    self.pomo_cycle = (self.pomo_cycle % 4) + 1
                    self.selected_minutes = 25
                    self.start_timer()
                else:
                    self.is_running = False
                    self.reset_to_setup_view()

    def reset_to_setup_view(self):
        self.unblock_websites()
        self.is_overtime = False
        self.overtime_multiplier = 1.0
        self.continuation_count = 0
        self.chain_total_minutes = 0
        self.chain_clock_checks = 0
        self.youtube_bypassed = False
        self.youtube_permitted = False
        self.is_micro_commitment = False
        self.is_hall_pass = False
        if hasattr(self, 'boost_badge_lbl'):
            self.boost_badge_lbl.config(text="")
        if hasattr(self, 'yt_bypass_btn'):
            self.yt_bypass_btn.config(text="🔓 Unblock YouTube", bg="#1a1a1a", fg="#ff9800")
        if hasattr(self, 'hall_pass_btn'):
            self.hall_pass_btn.config(text="🚽 5m Hall Pass (1)", bg="#1a1a1a", fg="#00bcd4", state="normal")

        self.audio_card.pack_forget()
        self.root.configure(bg="#000000")
        self.canvas.configure(bg="#000000")
        self.audio_card.configure(bg="#121212")
        self.emerge_btn.place_forget()
        
        if hasattr(self, 'admin_banner') and not is_admin():
            self.admin_banner.pack(fill=tk.X, side=tk.TOP)
        self.top_card.pack(fill=tk.X, padx=15, pady=(10, 4))
        if hasattr(self, 'deadline_banner'):
            self.deadline_banner.pack(after=self.top_card, fill=tk.X, padx=15, pady=(2, 4))
            self.update_imminent_deadline_banner()
        self.mode_frame.pack(pady=2)
        self.stats_label.pack(pady=(2, 2))
        if self.mode == "custom":
            self.controls_frame.pack(pady=2)
        self.canvas.pack(pady=2)
        self.goals_card.pack(fill=tk.X, padx=15, pady=3)
        self.audio_card.pack(fill=tk.X, padx=15, pady=3)
        self.rank_card.pack(fill=tk.X, padx=15, pady=3)
        self.start_btn.pack(pady=4)
        if hasattr(self, 'micro_start_btn'):
            self.micro_start_btn.pack(pady=(0, 4))
        self.draw_clock(self.selected_minutes)

    def enforce_rules(self):
        if not psutil:
            return
        blocked_set = {app.lower().strip() for app in self.blocked_apps if app.strip()}
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info.get('name')
                if name and name.lower() in blocked_set:
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

    # --- Stop Protocol ---
    def trigger_stop_protocol(self):
        if hasattr(self, 'stop_frame') and self.stop_frame.winfo_exists():
            return
        if hasattr(self, 'hall_pass_frame') and self.hall_pass_frame.winfo_exists():
            self.end_hall_pass()
        self.hide_peek()

        self.stop_frame = tk.Frame(self.root, bg="#121212", highlightbackground="#333333", highlightthickness=2)
        self.stop_frame.place(relx=0.5, rely=0.5, anchor="center", width=390, height=350)

        tk.Label(self.stop_frame, text="To stop, type the following exactly:", font=("Segoe UI", 9, "bold"), bg="#121212", fg="#ffffff").pack(pady=(15, 5))
        target_lbl = tk.Message(self.stop_frame, text=self.stop_phrase, font=("Segoe UI", 8, "italic"), bg="#000000", fg="#cccccc", width=350)
        target_lbl.pack(pady=5, padx=10)

        self.type_area = tk.Text(self.stop_frame, height=5, width=48, font=("Segoe UI", 8), bg="#1f1f1f", fg="white", wrap=tk.WORD, bd=0)
        self.type_area.pack(pady=5)

        self.error_label = tk.Label(self.stop_frame, text="", font=("Segoe UI", 8), bg="#121212", fg="#f44336")
        self.error_label.pack()

        btn_frame = tk.Frame(self.stop_frame, bg="#121212")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Verify & Stop", font=("Segoe UI", 8, "bold"), bg="#f44336", fg="white", relief="flat", command=self.verify_stop).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", font=("Segoe UI", 8), bg="#333333", fg="white", relief="flat", command=self.cancel_stop).pack(side=tk.LEFT, padx=5)

    def verify_stop(self):
        user_text = self.type_area.get("1.0", tk.END).strip().lower()
        target_text = self.stop_phrase.lower()

        user_clean = user_text.translate(str.maketrans('', '', string.punctuation))
        target_clean = target_text.translate(str.maketrans('', '', string.punctuation))

        user_clean = ' '.join(user_clean.split())
        target_clean = ' '.join(target_clean.split())

        if user_clean == target_clean:
            elapsed_seconds = (self.selected_minutes * 60) - self.time_left
            elapsed_minutes = elapsed_seconds // 60
            if elapsed_minutes > 0 and not self.is_break:
                reward_m = int(round(elapsed_minutes * self.overtime_multiplier)) if self.is_overtime else elapsed_minutes
                self.record_completed_session(elapsed_minutes, completed=False, reward_minutes=reward_m)

            self.is_running = False
            self.is_overtime = False
            self.overtime_multiplier = 1.0
            self.continuation_count = 0
            self.chain_total_minutes = 0
            self.chain_clock_checks = 0
            self.unblock_websites() 
            self.root.destroy()
        else:
            self.error_label.config(text="Incorrect. Missing words or wrong order.")

    def cancel_stop(self):
        self.stop_frame.destroy()

if __name__ == "__main__":
    is_startup = "--startup-check" in sys.argv
    root = tk.Tk()
    app = FocusApp(root, is_startup_mode=is_startup)
    root.mainloop()
