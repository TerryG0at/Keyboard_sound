# Keyboard Sound

A lightweight Windows desktop app that plays a local WAV or MP3 sound whenever a keyboard key is pressed. The app uses `tkinter` for the UI, `pynput` for global keyboard events, `pygame` for playback, and `pystray` for tray behavior.

## Setup

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

## Usage

- Use **Enable Sound** / **Disable Sound** to toggle playback immediately.
- Use the volume slider from 0% to 400%. Values above 100% boost quiet recordings, up to four times their original amplitude. The boost stops increasing when the recording reaches its peak limit.
- Use **Choose Sound** to select a custom `.wav` or `.mp3` file.
- Use **Minimize to Tray** or close the window to keep the app running in the background.
- Use the tray menu to show the window, toggle sound, or exit completely.

Settings are saved to:

```text
%APPDATA%\KeyboardSound\settings.json
```

## Audio Asset

`assets/shotgun.wav` is a generated placeholder click sound, not a real shotgun recording. Use **Choose Sound** to select any short `.wav` or `.mp3` file you prefer. Short sounds work best because they keep rapid typing responsive.

## Rapid Typing

Sounds are decoded, boosted, and cached when selected. Leading digital silence is removed, with 2 ms retained before the attack. Key presses play immediately without a queue or a default cooldown. The playback pool starts at 64 simultaneous sounds and grows to 256; active sounds are never stolen to play another key.

Pressing the same key consecutively plays sound on the first four presses. The fifth and further presses of that key trigger no new sound, allowing the first four sounds to finish naturally. Pressing a different key immediately restores playback and resets the count. This includes held-key auto-repeat and repeated Backspace presses. Releasing the key or waiting does not reset the count. Only the latest key and its repeat count are held temporarily in memory; key presses are never logged or saved.

The old default 50 ms cooldown is automatically migrated to 0 ms. Custom cooldown settings are preserved. Settings writes and sound processing do not hold the locks used by key playback.

Use a short sound (about 50-200 ms) for the clearest response during fast typing. Very long recordings overlap and can still fill all 256 slots, at which point new sounds are skipped rather than delayed. Overlapping loud sounds can distort even when each individual recording is peak-limited; lower the volume if that happens. Windows audio-device latency still applies.

## Run Tests

```powershell
python -m unittest discover -s tests
```

The tests cover configuration loading/saving, supported audio formats, load errors, and the playback cooldown behavior without requiring a real audio device.

## Build a Windows EXE

Install dependencies first, then run:

```powershell
python -m PyInstaller --noconsole --onefile --name KeyboardSound --icon assets/keyboard.ico --add-data "assets;assets" --hidden-import pynput.keyboard._win32 --hidden-import pystray._win32 main.py
```

The executable will be created under:

```text
dist\KeyboardSound.exe
```

The EXE includes Python, its dependencies, and bundled WAV/MP3 sounds. Double-click it to open the app. An existing instance remains in the tray if the EXE is opened again.

## Install And Start With Windows

After building, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
```

This installs the EXE to `%LOCALAPPDATA%\Programs\KeyboardSound`, creates a desktop shortcut, and creates a current-user Startup shortcut. It starts in the system tray at the next Windows sign-in, using your existing settings. No administrator access or Python installation is needed to run the EXE.

To disable automatic startup, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1 -RemoveStartup
```

To update the installed app, exit it through the tray menu, rebuild, and run the installation script again.
