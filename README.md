# FocusFlow

A distraction-blocking study timer for Windows and Android built to stay on top of university deadlines and get deep work done.

Instead of just ringing a bell like standard Pomodoro apps, it aggressively blocks websites and games at the system level, syncs directly with your university Moodle calendar, lets you set real-life rewards for hitting study goals, and pairs with an **Android Mobile Companion** to lock down phone distractions in real time.

---

## Features

### 🖥️ Desktop (Windows)
- **All-in-One Standalone Executable**: All you need to download and run is **`focus_app.exe`**. Python runtime, background sync bridge, and mobile APK are all bundled inside.
- **Hardcore Distraction Blocker**: Modifies your Windows hosts file to block distracting sites (YouTube, Reddit, Twitch, Twitter/X, Netflix, etc.) and kills game launchers (Steam, Discord, Tarkov, VR runtimes).
- **Emergency Exit**: If you really need to break out early, you have to type out a full focus commitment statement verbatim to stop impulsive quitting.
- **Hall Pass**: Need a quick glass of water or a bathroom break? Take a 5-minute timed pause without failing the session.
- **Interactive Radial Timer**: Drag the analog clock hand to dial in whatever time you want, from a quick 5-minute warm-up to a 2-hour deep session.
- **Flow Momentum Overtime**: If you're in the zone when the timer hits zero, don't stop. Opt into overtime to keep riding the momentum with extra reward points.
- **Moodle & iCal Sync**: Paste your university calendar export link (`webcal://` or `https://`). It automatically imports upcoming deadlines, detects date changes, and lets you filter recurring lectures.
- **Post-Session Reflection**: Logs friction levels, distraction triggers, and clock checks. Generates clean notes you can paste into your study journal or Notion.
- **Real-Life Milestone Rewards**: Set your own rewards for hitting milestone hours (e.g. Tier 1 at 2h = coffee break, Tier 3 at 5h = gaming night).
- **Embedded YouTube Audio Player**: Paste any YouTube link (such as lofi hip hop or synthwave) to stream music without recommendations, sidebars, or comments.
- **Built-in Auto-Updater**: Checks GitHub Releases on startup and updates itself with one click.

### 📱 Mobile Companion (Android)
- **Real-Time Wi-Fi Sync**: Seamlessly syncs timer, streak count, deadlines, and rewards between PC and phone over local Wi-Fi.
- **Automatic Do Not Disturb**: Mutes all incoming notifications the moment a focus session begins on your PC.
- **Continuous Sitting Limits**: Set per-session limits on any app (e.g. 15m/session on YouTube, Instagram, or TikTok) with an enforced 3-minute cooldown to stop doomscroll relapse.
- **7:00 AM Morning Fuel**: Starts your day at 7:00 AM with high-impact discipline and mindset quotes.
- **9:00 PM Bedtime Blocker & Overlay**: Actively closes distracting apps (like Gemini or social media) past 9:00 PM, kicks to the home screen, and displays a full-screen wind-down overlay with "+5m Wind Down" and "Put Phone Away" actions.
- **Silent Background Guardian**: Runs silently without cluttering your status bar, with an in-app toggle to turn off background monitoring whenever you want.

---

## Download & Quick Start

1. Download **`focus_app.exe`** from the [Releases](https://github.com/caecitas-glitch/Study-focus-app/releases/latest) page.
2. Put `focus_app.exe` in its own folder (like `C:\FocusFlow\` or on your Desktop).
3. **Right-click -> Run as Administrator**.  
   *(Admin rights are required to edit the Windows hosts file during a session to block websites and restore them when done).*

### Pairing Your Android Phone:
1. When `focus_app.exe` starts, click the **"📱 Phone Sync"** button on the dashboard to view your local Wi-Fi URL (e.g., `http://192.168.1.100:5050`).
2. Open that URL in your phone's browser and tap **Download Companion APK** (or install the bundled APK from the `mobile_companion/` folder).
3. In the mobile app, enter the address shown on your PC and tap **Sync**. Everything connects automatically.

All study history, tags, deadlines, and streak count are stored locally in `focus_data.json`. No cloud accounts or subscriptions required.

---

## Running from Source

If you want to run or modify the Python code directly:

```bash
# Clone the repository
git clone https://github.com/caecitas-glitch/Study-focus-app.git
cd Study-focus-app

# Run the app (requires Python 3.10+)
python Focus_app.pyw
```

### Compiling to a Standalone .exe
```bash
pip install pyinstaller flask psutil
python -m PyInstaller --noconfirm focus_app.spec
```
The output executable will be generated in `dist/focus_app.exe`.

---

## License
MIT License. Feel free to use, modify, or fork.
