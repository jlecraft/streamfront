"""
Initializes streamfront for first-time use:
  - Generates launch.bat using the script's own directory
  - Creates channels.txt if it does not exist
  - Creates category.txt if it does not exist
  - Creates a documented config.ini if one does not exist
  - Creates a Desktop shortcut pointing to launch.bat

Run once: python init.py
"""

import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent
BAT      = BASE_DIR / "launch.bat"
ICON     = BASE_DIR / "icon.ico"
DESKTOP  = Path(os.environ["USERPROFILE"]) / "Desktop"
SHORTCUT = DESKTOP / "streamfront.lnk"

# --- launch.bat ---
bat_content = '@echo off\nstart "" "pythonw.exe" "%~dp0main.py"\n'
BAT.write_text(bat_content)
print(f"Generated: {BAT}")

# --- channels.txt ---
channels_file = BASE_DIR / "channels.txt"
if not channels_file.exists():
    channels_file.write_text(
        "# One Twitch login per line.\n"
        "# Optional display name after a space: impulsesv Impulse\n"
        "# No display name → login shown in ALL CAPS.\n"
    )
    print(f"Created:   {channels_file}")
else:
    print(f"Exists:    {channels_file} (skipped)")

# --- category.txt ---
category_file = BASE_DIR / "category.txt"
if not category_file.exists():
    category_file.write_text(
        "# Category keywords (one per line, case-insensitive).\n"
        "# If a live stream's category contains any keyword,\n"
        "# it is highlighted light blue in the UI.\n"
        "# minecraft\n"
        "# just chatting\n"
    )
    print(f"Created:   {category_file}")
else:
    print(f"Exists:    {category_file} (skipped)")

# --- config.ini ---
config_file = BASE_DIR / "config.ini"
if not config_file.exists():
    config_file.write_text(
        "# streamfront configuration\n"
        "# All sections and keys are optional.\n"
        "\n"
        "[player]\n"
        "# Full path to your media player executable.\n"
        "# When set, streamlink will pass --player to open streams in this player.\n"
        "# Leave commented out (or remove the section) to omit --player entirely.\n"
        "# path = C:\\Path\\To\\Player.exe\n"
        "\n"
        "[twitch]\n"
        "# Twitch API credentials for live status (viewer counts, titles, categories).\n"
        "# Create an app at https://dev.twitch.tv/console to obtain these values.\n"
        "# Without credentials, live status checking is disabled.\n"
        "# client_id = your_client_id_here\n"
        "# client_secret = your_client_secret_here\n"
    )
    print(f"Created:   {config_file}")
else:
    print(f"Exists:    {config_file} (skipped)")

# --- Desktop shortcut ---
ps = f"""
$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{SHORTCUT}')
$s.TargetPath       = '{BAT}'
$s.IconLocation     = '{ICON}'
$s.WorkingDirectory = '{BASE_DIR}'
$s.Description      = 'Launch streamfront'
$s.Save()
"""
subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
print(f"Shortcut:  {SHORTCUT}")
