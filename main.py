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
        channels.append({"name": name, "url": url, "login": login, "index": len(channels)})
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


def fetch_live_data(logins: list[str], client_id: str, token: str) -> dict[str, int]:
    """Return a dict mapping login name → viewer count for all currently live channels."""
    live: dict[str, int] = {}
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
                login = stream["user_login"].lower()
                live[login] = stream.get("viewer_count", 0)
        except Exception:
            pass
    return live


def _fmt_viewers(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M viewers"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K viewers"
    return f"{n} viewers"




# ── Main application ──────────────────────────────────────────────────────────

class App(ctk.CTk):
    REFRESH_INTERVAL_MS = 60_000  # auto-refresh every 60 seconds
    DOT_LIVE = "#2ecc71"          # green
    DOT_OFFLINE = "#555555"       # dark gray
    HOVER_BG = ("#e0e0e0", "#3a3a3a")

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
        self._countdown_job = None

        self._build_ui()
        self._initial_status_refresh()
        if self.api_enabled:
            self._countdown_remaining = self.REFRESH_INTERVAL_MS // 1000
            self._countdown_job = self.after(1000, self._tick_countdown)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("TwitchLauncher")
        self.geometry("480x660")
        self.minsize(400, 400)
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
            text="↻",
            width=36,
            height=36,
            font=ctk.CTkFont(size=20),
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

        # Countdown bar (visible only when API is enabled)
        if self.api_enabled:
            self.countdown_bar = ctk.CTkProgressBar(self, height=4, corner_radius=0)
            self.countdown_bar.pack(fill="x", padx=16, pady=(2, 0))
            self.countdown_bar.set(1.0)

        # Scrollable channel list
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(4, 4))

        if not self.channels:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No channels found.\nEdit channels.txt to add some.",
                font=ctk.CTkFont(size=13),
                text_color="#888888",
            ).pack(pady=40)
        else:
            for i, ch in enumerate(self.channels):
                self._add_channel_row(i, ch)

        # Log output area
        ctk.CTkLabel(self, text="Output", font=ctk.CTkFont(size=12),
                     text_color="#888888").pack(anchor="w", padx=16)
        self.log_box = ctk.CTkTextbox(self, height=130, font=ctk.CTkFont(family="Courier", size=11),
                                      state="disabled", wrap="word")
        self.log_box.pack(fill="x", padx=16, pady=(0, 16))

    def _add_channel_row(self, row: int, ch: dict, is_live: bool = False, viewer_count: int = 0) -> None:
        launch = lambda e=None, n=ch["name"], url=ch["url"]: self._launch_stream(n, url)

        # Row frame — hover highlight covers the full row
        row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent", cursor="hand2")
        row_frame.pack(fill="x", pady=1)
        row_frame.bind("<Button-1>", launch)

        def on_enter(e):
            row_frame.configure(fg_color=self.HOVER_BG)

        def on_leave(e):
            # Only unhighlight if the cursor has genuinely left the row frame
            x, y = e.x_root, e.y_root
            rx, ry = row_frame.winfo_rootx(), row_frame.winfo_rooty()
            rw, rh = row_frame.winfo_width(), row_frame.winfo_height()
            if not (rx <= x < rx + rw and ry <= y < ry + rh):
                row_frame.configure(fg_color="transparent")

        # Status dot
        dot = ctk.CTkLabel(
            row_frame,
            text="●",
            font=ctk.CTkFont(size=14),
            text_color=self.DOT_LIVE if is_live else self.DOT_OFFLINE,
            width=24,
            fg_color="transparent",
            cursor="hand2",
        )
        dot.pack(side="left", padx=(4, 6), pady=6)
        dot.bind("<Button-1>", launch)
        dot.bind("<Enter>", on_enter)
        dot.bind("<Leave>", on_leave)
        if ch["login"]:
            self._dot_labels[ch["login"]] = dot

        # Viewer count (packed right first so name fills remaining space)
        count_text = _fmt_viewers(viewer_count) if is_live and viewer_count > 0 else ""
        count_label = ctk.CTkLabel(
            row_frame,
            text=count_text,
            font=ctk.CTkFont(size=12),
            text_color="#888888",
            anchor="e",
            width=100,
            fg_color="transparent",
            cursor="hand2",
        )
        count_label.pack(side="right", padx=(0, 8), pady=6)
        count_label.bind("<Button-1>", launch)
        count_label.bind("<Enter>", on_enter)
        count_label.bind("<Leave>", on_leave)

        # Channel name
        name_label = ctk.CTkLabel(
            row_frame,
            text=ch["name"],
            font=ctk.CTkFont(size=14),
            anchor="w",
            fg_color="transparent",
            cursor="hand2",
        )
        name_label.pack(side="left", fill="x", expand=True, padx=4, pady=6)
        name_label.bind("<Button-1>", launch)
        name_label.bind("<Enter>", on_enter)
        name_label.bind("<Leave>", on_leave)

    # ── Stream launcher ───────────────────────────────────────────────────────

    def _launch_stream(self, name: str, url: str) -> None:
        cmd = ["streamlink", "--player", self.player, url, self.quality]
        self._log(name, f"Starting: {' '.join(cmd)}")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            threading.Thread(target=self._read_output, args=(name, proc), daemon=True).start()
        except FileNotFoundError:
            self._log(name, "ERROR: streamlink not found in PATH")
            msgbox.showerror(
                "streamlink not found",
                "Could not find streamlink in your PATH.\n\n"
                "Install it with:  pip install streamlink\n"
                "or from:          https://streamlink.github.io",
            )

    def _read_output(self, name: str, proc: subprocess.Popen) -> None:
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self.after(0, lambda l=line: self._log(name, l))
        self.after(0, lambda: self._log(name, "Stream ended."))

    def _log(self, name: str, line: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{name}] {line}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ── Countdown bar ─────────────────────────────────────────────────────────

    def _reset_countdown(self) -> None:
        if self._countdown_job:
            self.after_cancel(self._countdown_job)
        self._countdown_remaining = self.REFRESH_INTERVAL_MS // 1000
        self.countdown_bar.set(1.0)
        self._countdown_job = self.after(1000, self._tick_countdown)

    def _tick_countdown(self) -> None:
        self._countdown_remaining -= 1
        progress = max(0.0, self._countdown_remaining / (self.REFRESH_INTERVAL_MS // 1000))
        self.countdown_bar.set(progress)
        if self._countdown_remaining > 0:
            self._countdown_job = self.after(1000, self._tick_countdown)
        else:
            self._countdown_job = None

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
        self.refresh_btn.configure(state="disabled")
        threading.Thread(target=self._manual_refresh_worker, daemon=True).start()

    def _manual_refresh_worker(self) -> None:
        if self.token is None:
            self.token = get_app_token(self.client_id, self.client_secret)
        if self.token:
            self._do_status_refresh()
        self.after(0, lambda: self.refresh_btn.configure(state="normal"))

    def _do_status_refresh(self) -> None:
        logins = [ch["login"] for ch in self.channels if ch["login"]]
        if not logins or not self.token:
            return
        live = fetch_live_data(logins, self.client_id, self.token)
        self.after(0, lambda: self._apply_status(live))

    def _apply_status(self, live: set[str]) -> None:
        if self.api_enabled:
            self._reset_countdown()

        # Sort live channels to the top, preserving original file order within each group
        self.channels.sort(key=lambda ch: (0 if ch["login"] in live else 1, ch["index"]))

        # Rebuild the channel rows in sorted order
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self._dot_labels.clear()

        for i, ch in enumerate(self.channels):
            is_live = bool(ch["login"] and ch["login"] in live)
            count = live.get(ch["login"], 0) if ch["login"] else 0
            self._add_channel_row(i, ch, is_live=is_live, viewer_count=count)


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
