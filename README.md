# FocusFlow

A distraction-blocking study timer for Windows that I built to stay on top of university deadlines and actually get deep work done.

Instead of just ringing a bell like standard Pomodoro apps, it aggressively blocks websites and games at the system level, syncs directly with your university Moodle calendar, and lets you set real-life rewards for hitting study goals.

---

## Features

- **Hardcore Distraction Blocker**: Modifies your Windows hosts file to block distracting sites (YouTube, Reddit, Twitch, Twitter/X, Netflix, etc.) and kills game launchers (Steam, Discord, Tarkov, VR runtimes).
- **Emergency Exit**: If you really need to break out early, you have to type out a full focus commitment statement verbatim to stop impulsive quitting.
- **Hall Pass**: Need a quick glass of water or a bathroom break? Take a 5-minute timed pause without failing the session.
- **Interactive Radial Timer**: Drag the analog clock hand to dial in whatever time you want, from a quick 5-minute warm-up to a 2-hour deep session.
- **Flow Momentum Overtime**: If you're in the zone when the timer hits zero, don't stop. Opt into overtime to keep riding the momentum with extra reward points.
- **Moodle & iCal Sync**: Paste your university calendar export link (`webcal://` or `https://`). It automatically imports your upcoming deadlines, detects when professors push dates back, and lets you batch-mark recurring attendance / lecture sessions so they don't clutter your urgent tasks.
- **Post-Session Reflection**: Logs friction levels, distraction triggers, and how many times you checked the clock during your session. Generates clean notes you can copy-paste into your study journal or Notion.
- **Real-Life Milestone Rewards**: Set your own rewards for hitting milestone hours (e.g. Tier 1 at 2h = coffee break, Tier 3 at 5h = movie or gaming night).
- **Background Sound**: Built-in rain sounds, classical tracks, or an embedded YouTube audio player with zero recommendations or comments.
- **Built-in Auto-Updater**: Checks GitHub Releases on startup and updates itself with one click.

---

## Customization

FocusFlow is designed to adapt to your actual study setup and habits rather than forcing a rigid system:

- **Custom Website & App Blocklists**:
  Open the **Blocker** tab in Settings to add or remove sites and desktop applications. You can add any URL to block via the Windows hosts file, or add any process name (`.exe`) to block games and launchers from running while you study.
- **Course Tags & Weekly Targets**:
  Set up custom `#tags` for your courses or projects (e.g. `#Calculus`, `#DataStructures`, `#Thesis`). In the **Analytics** tab, you can assign weekly study hour goals to each tag so you can see if you're balancing your coursework or neglecting a difficult class.
- **Custom Milestone Rewards**:
  In the **Rewards** tab, customize both the time thresholds and the rewards. You set what each tier gives you (e.g., 2 hours = favorite snack, 5 hours = gaming night guilt-free). The app tracks your cumulative focus time toward the next unlock.
- **Custom Audio & Lo-Fi Streams**:
  Switch between offline looping rain, classical piano tracks, or paste any YouTube link (such as a 24/7 lofi hip hop or synthwave stream). FocusFlow embeds the video directly without comments, recommended sidebars, or homepage algorithms.
- **Pre-Designated Lock-in Sessions**:
  Schedule a study session ahead of time (choose the date, duration, and subject tag). The next time you open the app on that day, it automatically presents your planned session so you can jump straight in without decision fatigue.
- **Plain JSON Configuration**:
  All settings, blocklists, deadlines, and study history are stored in a standard `focus_data.json` file next to the app. You can back it up, move it to another PC, or inspect it anytime.

---

## Download & Usage

1. Download **`focus_app.exe`** from the [Releases](https://github.com/caecitas-glitch/Study-focus-app/releases/latest) page.
2. Put `focus_app.exe` in its own folder (like `C:\FocusFlow\` or on your Desktop).
3. **Right-click -> Run as Administrator**.  
   *(Admin rights are strictly required to edit the Windows hosts file during a session to block websites and restore them when done).*

All your study history, tags, deadlines, and streak count are stored locally in a `focus_data.json` file in the same folder. Nothing is sent to any external server.

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

### Compiling to an .exe
```bash
pip install pyinstaller
python -m PyInstaller --noconfirm focus_app.spec
```
The output executable will be generated in `dist/focus_app.exe`.

---

## License
MIT License. Feel free to use, modify, or fork.
