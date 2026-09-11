# 🎯 FocusFlow — Deep Work & Study Productivity Engine

> A high-leverage Windows desktop focus companion engineered for deep work, university course tracking, and elimination of digital distractions.

---

## ⚡ Key Features

### 🛡️ System-Level Distraction Shield
- **Website Blocking**: Instantly blocks social media, video feeds, and custom distraction sites during focus sessions via safe hosts filtering.
- **Application Blocker**: Silences game launchers (Steam, Discord, Tarkov, VR runtimes, etc.) to keep you locked in.
- **Emergency Emerge**: Need an emergency breakout? Face a penalty timer and mental math puzzle to verify intentional exits.
- **Hall Pass Micro-Breaks**: Take a timed 3-minute biological break without aborting your session or dropping your flow.

### ⏳ Interactive Drag Timer & Visual Clock
- **Smooth Radial Dragging**: Seamlessly set session durations from 5-minute *Zeigarnik* micro-commitments to multi-hour deep study sprints.
- **Stealth Peek Mode**: Hover to preview remaining time without constant clock-watching anxiety.
- **Clock-Check Audit**: Tracks how many times you checked the clock during a session to measure attention wandering.

### 🔥 Flow State Momentum Booster
- When your focus timer rings, don't let artificial breaks kill your momentum.
- Opt into **Overtime Boost** (1.25x / 1.5x reward multipliers) to ride your natural cognitive flow.

### 📅 Live Moodle & iCal Calendar Sync
- **Subscription URL Support**: Point to your university's iCal/webcal feed (Moodle, Canvas, Blackboard, Google Calendar) for automatic sync.
- **Smart Deadline Tracking**: Detects rescheduled assignments, auto-updates due dates without duplicates, and recommends tailored study durations.
- **Batch Management**: Mark attendance (*Läsnäolo*) or completed assignments with 1 click so they never clutter upcoming urgency alerts.

### 📝 End-of-Session Reflection & Productivity Survey
- Quantify your study sessions with a scientific friction and focus audit:
  - Work Type (Deep Problem Solving, Memorization, Writing, etc.)
  - Starting Friction & Trigger Analysis
  - Distraction Audit (Phone, Tabs, Environment)
  - Physical Calibration (Caffeine, Sleep, Pacing)
- **1-Click Export**: Format your reflection cleanly for personal study logs, Notion, or journal archives.

### 🏆 Gamified Progression & Real-Life Rewards
- **Tiered Rewards**: Unlock real-life treats you define (e.g., Apprentice at 120m, Master at 300m, Apex Scholar at 1000m).
- **Study Streaks & Badges**: Build momentum with consecutive study days and earn milestone achievements.
- **Course Targets**: Set custom hour goals across specific subjects and watch your progress bars advance.

### 🌧️ Distraction-Free Audio
- Built-in soothing rain synthesizer, classical focus compositions, and a distraction-free custom YouTube stream player (embed mode with zero recommendations or comment feeds).

---

## 🚀 Getting Started

### Pre-built Executable (Recommended for Testers)
1. Download the latest ocus_app.exe from the [Releases](https://github.com/) tab.
2. Place ocus_app.exe into a dedicated folder (e.g., C:\FocusApp\ or your desktop).
3. **Run as Administrator** (required for the website and process distraction blocker to modify system host bindings).
4. All your personal metrics, streaks, and settings are saved automatically in a local ocus_data.json file in the same folder.

---

## 🛠️ Building from Source

### Prerequisites
- Windows 10 or 11 (64-bit)
- Python 3.10+ (Recommended Python 3.12 - 3.14)

### Setup & Run
`ash
# Clone the repository
git clone https://github.com/your-username/focus-app.git
cd focus-app

# (Optional) Install psutil for enhanced process management
pip install psutil

# Run directly
python Focus_app.pyw
`

### Compiling to Standalone .exe
`ash
pip install pyinstaller
pyinstaller --noconfirm focus_app.spec
`
The compiled standalone executable will be located in the dist/ directory.

---

## 🔒 Privacy & Safety
- **100% Local**: No telemetry, no external database, no login credentials required.
- **Safe Hosts Cleanup**: The app uses strict boundary markers in Windows hosts files and automatically cleans up all block rules on application exit or shutdown.
- **Personal Data**: Your study notes, reflections, and calendar tokens stay strictly on your local machine (ocus_data.json).

---

## 📄 License
MIT License. Free to use, adapt, and study.
