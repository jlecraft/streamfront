"""
TwitchLauncher - A GUI front-end for streamlink.
Reads channels from channels.txt and presents a one-click launch list.
"""

import configparser
import subprocess
import threading
import re
import sys
import os
import tkinter as tk
import tkinter.messagebox as msgbox
from pathlib import Path

import customtkinter as ctk
import requests

# ── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
CHANNELS_FILE = BASE_DIR / "channels.txt"
CONFIG_FILE = BASE_DIR / "config.ini"

# ── Configuration ─────────────────────────────────────────────────────────────

def load_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg["streamlink"] = {"quality": "best", "player": "vlc"}
    cfg["twitch_api"] = {"client_id": "", "client_secret": ""}
    if CONFIG_FILE.exists():
        cfg.read(CONFIG_FILE)
    return cfg


# ── Channel parsing ───────────────────────────────────────────────────────────

def parse_channels(path: Path) -> list[dict]:
    """Return list of {name, url, login} dicts from channels.txt."""
    channels = []
    if not path.exists():
        return channels
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            name, _, url = line.partition("|")
            name, url = name.strip(), url.strip()
        else:
            url = line.strip()
            name = url
        login = extract_twitch_login(url)
        channels.append({"name": name, "url": url, "login": login})
    return channels


def extract_twitch_login(url: str) -> str | None:
    """Extract the Twitch login name from a twitch.tv URL."""
    match = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", url)
    return match.group(1).lower() if match else None


# ── Twitch API ────────────────────────────────────────────────────────────────

def get_app_token(client_id: str, client_secret: str) -> str | None:
    """Fetch a Twitch app access token via client credentials grant."""
    try:
        resp = requests.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception:
        return None


def fetch_live_logins(logins: list[str], client_id: str, token: str) -> set[str]:
    """Return the set of login names that are currently live."""
    live = set()
    # API accepts up to 100 logins per request
    for i in range(0, len(logins), 100):
        chunk = logins[i : i + 100]
        params = [("user_login", login) for login in chunk]
        try:
            resp = requests.get(
                "https://api.twitch.tv/helix/streams",
                params=params,
                headers={"Client-ID": client_id, "Authorization": f"Bearer {token}"},
                timeout=10,
            )
            resp.raise_for_status()
            for stream in resp.json().get("data", []):
                live.add(stream["user_login"].lower())
        except Exception:
            pass
    return live


# ── Stream launcher ───────────────────────────────────────────────────────────

def launch_stream(url: str, quality: str, player: str) -> None:
    """Fire-and-forget: launch streamlink in a background process."""
    cmd = ["streamlink", "--player", player, url, quality]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except FileNotFoundError:
        msgbox.showerror(
            "streamlink not found",
            "Could not find streamlink in your PATH.\n\n"
            "Install it with:  pip install streamlink\n"
            "or from:          https://streamlink.github.io",
        )


# ── Main application ──────────────────────────────────────────────────────────

class App(ctk.CTk):
    REFRESH_INTERVAL_MS = 60_000  # auto-refresh every 60 seconds
    DOT_LIVE = "#2ecc71"          # green
    DOT_OFFLINE = "#555555"       # dark gray

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.quality = self.cfg.get("streamlink", "quality", fallback="best")
        self.player = self.cfg.get("streamlink", "player", fallback="vlc")
        self.client_id = self.cfg.get("twitch_api", "client_id", fallback="").strip()
        self.client_secret = self.cfg.get("twitch_api", "client_secret", fallback="").strip()
        self.api_enabled = bool(self.client_id and self.client_secret)
        self.token: str | None = None

        self.channels = parse_channels(CHANNELS_FILE)
        self._dot_labels: dict[str, ctk.CTkLabel] = {}  # login → dot label
        self._refresh_job = None

        self._build_ui()
        self._initial_status_refresh()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("TwitchLauncher")
        self.geometry("480x520")
        self.minsize(400, 300)
        self.resizable(True, True)

        icon = BASE_DIR / "icon.ico"
        if icon.exists():
            self.iconbitmap(str(icon))

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(header, text="TwitchLauncher", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            header,
            text="Refresh",
            width=90,
            command=self._manual_refresh,
        )
        self.refresh_btn.pack(side="right")

        if not self.api_enabled:
            ctk.CTkLabel(
                self,
                text="Live status disabled — add Twitch API credentials to config.ini",
                font=ctk.CTkFont(size=11),
                text_color="#888888",
            ).pack(padx=16, anchor="w")

        # Scrollable channel list
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self.scroll_frame.grid_columnconfigure(1, weight=1)

        if not self.channels:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No channels found.\nEdit channels.txt to add some.",
                font=ctk.CTkFont(size=13),
                text_color="#888888",
            ).grid(row=0, column=0, columnspan=3, pady=40)
        else:
            for i, ch in enumerate(self.channels):
                self._add_channel_row(i, ch)

    def _add_channel_row(self, row: int, ch: dict, is_live: bool = False) -> None:
        # Status dot
        dot = ctk.CTkLabel(
            self.scroll_frame,
            text="●",
            font=ctk.CTkFont(size=14),
            text_color=self.DOT_LIVE if is_live else self.DOT_OFFLINE,
            width=24,
        )
        dot.grid(row=row, column=0, padx=(4, 6), pady=6, sticky="w")
        if ch["login"]:
            self._dot_labels[ch["login"]] = dot

        # Channel name
        ctk.CTkLabel(
            self.scroll_frame,
            text=ch["name"],
            font=ctk.CTkFont(size=14),
            anchor="w",
        ).grid(row=row, column=1, padx=4, pady=6, sticky="ew")

        # Watch button
        btn = ctk.CTkButton(
            self.scroll_frame,
            text="Watch ▶",
            width=100,
            command=lambda url=ch["url"]: launch_stream(url, self.quality, self.player),
        )
        btn.grid(row=row, column=2, padx=(8, 4), pady=6)

    # ── Live status ───────────────────────────────────────────────────────────

    def _initial_status_refresh(self) -> None:
        if not self.api_enabled:
            return
        threading.Thread(target=self._authenticate_and_refresh, daemon=True).start()

    def _authenticate_and_refresh(self) -> None:
        if self.token is None:
            self.token = get_app_token(self.client_id, self.client_secret)
        if self.token:
            self._do_status_refresh()
        # Schedule next auto-refresh on the main thread
        self.after(self.REFRESH_INTERVAL_MS, self._schedule_refresh)

    def _schedule_refresh(self) -> None:
        if self.api_enabled:
            threading.Thread(target=self._authenticate_and_refresh, daemon=True).start()

    def _manual_refresh(self) -> None:
        if not self.api_enabled:
            msgbox.showinfo(
                "API not configured",
                "Add your Twitch client_id and client_secret to config.ini to enable live status.",
            )
            return
        self.refresh_btn.configure(state="disabled", text="Refreshing…")
        threading.Thread(target=self._manual_refresh_worker, daemon=True).start()

    def _manual_refresh_worker(self) -> None:
        if self.token is None:
            self.token = get_app_token(self.client_id, self.client_secret)
        if self.token:
            self._do_status_refresh()
        self.after(0, lambda: self.refresh_btn.configure(state="normal", text="Refresh"))

    def _do_status_refresh(self) -> None:
        logins = [ch["login"] for ch in self.channels if ch["login"]]
        if not logins or not self.token:
            return
        live = fetch_live_logins(logins, self.client_id, self.token)
        self.after(0, lambda: self._apply_status(live))

    def _apply_status(self, live: set[str]) -> None:
        # Sort live channels to the top, preserving original order within each group
        self.channels.sort(key=lambda ch: 0 if ch["login"] in live else 1)

        # Rebuild the channel rows in sorted order
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self._dot_labels.clear()

        for i, ch in enumerate(self.channels):
            self._add_channel_row(i, ch, is_live=bool(ch["login"] and ch["login"] in live))


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    # Ensure channels.txt exists with a helpful template
    if not CHANNELS_FILE.exists():
        CHANNELS_FILE.write_text(
            "# TwitchLauncher channel list\n"
            "# Format: Display Name | URL\n"
            "# Lines starting with # are ignored\n\n"
            "# Example:\n"
            "# xQc | https://twitch.tv/xqc\n",
            encoding="utf-8",
        )
        msgbox.showinfo(
            "channels.txt created",
            f"A template channels.txt was created at:\n{CHANNELS_FILE}\n\n"
            "Add your channels and restart the app.",
        )

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
