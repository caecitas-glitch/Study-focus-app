# FocusFlow

A distraction-blocking study timer for Windows that I built to stay on top of university deadlines and actually get deep work done.

Instead of just ringing a bell like standard Pomodoro apps, it aggressively blocks websites and games at the system level, syncs directly with your university Moodle calendar, and lets you set real-life rewards for hitting study goals.

---

## Features

- **Hardcore Distraction Blocker**: Modifies your Windows hosts file to block distracting sites (YouTube, Reddit, Twitch, Twitter/X, Netflix, etc.) and kills game launchers (Steam, Discord, Tarkov, VR runtimes).
- **Emergency Emerge**: If you really need to break out early, there is a penalty timer and a math puzzle to stop impulse tab-opening.
- **Hall Pass**: Need a quick glass of water or a bathroom break? Take a 3-minute timed pause without failing the session.
- **Interactive Radial Timer**: Drag the analog clock hand to dial in whatever time you want, from a quick 5-minute warm-up to a 2-hour deep session.
- **Flow Momentum Overtime**: If you're in the zone when the timer hits zero, don't stop. Opt into overtime to keep riding the momentum with extra reward points.
- **Moodle & iCal Sync**: Paste your university calendar export link (`webcal://` or `https://`). It automatically imports your upcoming deadlines, detects when professors push dates back, and lets you batch-mark attendance (*Läsnäolo*) so it doesn't clutter your urgent tasks.
- **Post-Session Reflection**: Logs friction levels, distraction triggers, and how many times you checked the clock during your session. Generates clean notes you can copy-paste into your study journal or Notion.
- **Real-Life Milestone Rewards**: Set your own rewards for hitting milestone hours (e.g. Apprentice at 2h = protein ice cream, Master at 5h = Burger King).
- **Background Sound**: Built-in rain sounds, classical tracks, or an embedded YouTube audio player with zero recommendations or comments.
- **Built-in Auto-Updater**: Checks GitHub Releases on startup and updates itself with one click.

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
