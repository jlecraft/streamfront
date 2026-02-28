"""
Creates a TwitchLauncher shortcut on the Desktop with the custom icon.
Run once: python create_shortcut.py
"""

import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent
BAT      = BASE_DIR / "launch.bat"
ICON     = BASE_DIR / "icon.ico"
DESKTOP  = Path(os.environ["USERPROFILE"]) / "Desktop"
SHORTCUT = DESKTOP / "TwitchLauncher.lnk"

ps = f"""
$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{SHORTCUT}')
$s.TargetPath     = '{BAT}'
$s.IconLocation   = '{ICON}'
$s.WorkingDirectory = '{BASE_DIR}'
$s.Description    = 'Launch TwitchLauncher'
$s.Save()
"""

subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
print(f"Shortcut created: {SHORTCUT}")
