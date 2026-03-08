"""
streamfront - A GUI front-end for streamlink.
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
CATEGORY_FILE = BASE_DIR / "category.txt"

# ── Configuration ─────────────────────────────────────────────────────────────

def load_category_keywords() -> list[str]:
    """Return lowercased keywords from category.txt."""
    if not CATEGORY_FILE.exists():
        return []
    return [
        line.strip().lower()
        for line in CATEGORY_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


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
        parts = line.split(None, 1)
        login = parts[0].lower()
        name = parts[1] if len(parts) > 1 else login.upper()
        url = f"https://www.twitch.tv/{login}"
        channels.append({"name": name, "url": url, "login": login, "index": len(channels)})
    return channels


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


def fetch_live_data(logins: list[str], client_id: str, token: str) -> dict[str, dict]:
    """Return a dict mapping login name → {viewers, title} for all currently live channels."""
    live: dict[str, dict] = {}
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
                live[login] = {
                    "viewers": stream.get("viewer_count", 0),
                    "title": stream.get("title", ""),
                    "category": stream.get("game_name", ""),
                }
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
    REFRESH_INTERVAL_MS = 60_000   # auto-refresh every 60 seconds
    COUNTDOWN_TICK_MS = 50         # countdown bar update interval (smooth animation)
    COUNTDOWN_STEPS = REFRESH_INTERVAL_MS // COUNTDOWN_TICK_MS  # 1200 steps
    DOT_LIVE = "#2ecc71"           # green
    DOT_OFFLINE = "#555555"        # dark gray
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
        self.category_keywords = load_category_keywords()
        self._row_widgets: dict[int, dict] = {}  # channel index → {frame, dot, count_label, title_label}
        self._refresh_job = None
        self._countdown_job = None
        self._ad_timer_job = None
        self._ad_seconds_remaining = 0

        self._build_ui()
        self._initial_status_refresh()
        if self.api_enabled:
            self._countdown_remaining = self.COUNTDOWN_STEPS
            self._countdown_job = self.after(self.COUNTDOWN_TICK_MS, self._tick_countdown)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("streamfront")
        self.geometry("1200x800")
        self.minsize(400, 400)
        self.resizable(True, True)

        icon = BASE_DIR / "icon.ico"
        if icon.exists():
            self.iconbitmap(str(icon))

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(header, text="streamfront", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")

        # Ad break timer (hidden until an ad is detected)
        self.ad_timer_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(family="Consolas", size=20),
            text_color="#e74c3c",
            fg_color="transparent",
            height=36,
            anchor="e",
        )
        self._attach_tooltip(self.ad_timer_label, "Time remaining on ad break")

        # Right-side container: refresh button with countdown bar directly beneath it
        right_frame = ctk.CTkFrame(header, fg_color="transparent")
        right_frame.pack(side="right")

        self.refresh_btn = ctk.CTkButton(
            right_frame,
            text="↻",
            width=36,
            height=36,
            font=ctk.CTkFont(size=20),
            command=self._manual_refresh,
        )
        self.refresh_btn.pack()

        if self.api_enabled:
            self.countdown_bar = ctk.CTkProgressBar(
                right_frame, width=36, height=4, corner_radius=0
            )
            self.countdown_bar.pack(pady=(2, 0))
            self.countdown_bar.set(0.0)

        if not self.api_enabled:
            ctk.CTkLabel(
                self,
                text="Live status disabled — add Twitch API credentials to config.ini",
                font=ctk.CTkFont(size=11),
                text_color="#888888",
            ).pack(padx=16, anchor="w")

        # Add streamer entry
        self.add_entry = ctk.CTkEntry(
            self,
            placeholder_text="Add a streamer...",
            font=ctk.CTkFont(size=13),
        )
        self.add_entry.pack(fill="x", padx=16, pady=(0, 6))
        self.add_entry.bind("<Return>", self._add_channel_from_entry)

        # Scrollable channel list
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(4, 4))

        self._empty_label = None
        if not self.channels:
            self._empty_label = ctk.CTkLabel(
                self.scroll_frame,
                text="No channels found. Add one above.",
                font=ctk.CTkFont(size=13),
                text_color="#888888",
            )
            self._empty_label.pack(pady=40)
        else:
            for i, ch in enumerate(self.channels):
                self._add_channel_row(i, ch)

        # Log output area
        ctk.CTkLabel(self, text="Output", font=ctk.CTkFont(size=12),
                     text_color="#888888").pack(anchor="w", padx=16)
        self.log_box = ctk.CTkTextbox(self, height=130, font=ctk.CTkFont(family="Courier", size=11),
                                      state="disabled", wrap="word")
        self.log_box.pack(fill="x", padx=16, pady=(0, 16))
        self.log_box._textbox.tag_configure("log_ad", foreground="#e74c3c")
        self.log_box._textbox.tag_configure("log_resume", foreground="#2ecc71")

    def _add_channel_row(self, row: int, ch: dict, is_live: bool = False, viewer_count: int = 0, title: str = "", category: str = "") -> None:
        launch = lambda e=None, n=ch["name"], url=ch["url"]: self._launch_stream(n, url)
        delete = lambda e, c=ch: (self._delete_channel(c), "break")[1]

        # Row frame — hover highlight covers the full row
        row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent", cursor="hand2")
        row_frame.pack(fill="x", pady=1)
        row_frame.bind("<Button-1>", launch)

        # Debounced hover: Leave schedules a clear after 20ms; Enter cancels it.
        # This prevents flicker when the mouse moves between children in the same row.
        _leave_job = [None]

        def on_enter(e):
            if _leave_job[0]:
                row_frame.after_cancel(_leave_job[0])
                _leave_job[0] = None
            row_frame.configure(fg_color=self.HOVER_BG)

        def on_leave(e):
            def do_clear():
                _leave_job[0] = None
                row_frame.configure(fg_color="transparent")
            _leave_job[0] = row_frame.after(20, do_clear)

        row_frame.bind("<Enter>", on_enter)
        row_frame.bind("<Leave>", on_leave)
        row_frame.bind("<Control-Button-1>", delete)

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
        dot.bind("<Control-Button-1>", delete)
        dot.bind("<Enter>", on_enter)
        dot.bind("<Leave>", on_leave)

        # Viewer count (packed right first so name fills remaining space)
        count_text = _fmt_viewers(viewer_count) if is_live and viewer_count > 0 else ""
        count_label = ctk.CTkLabel(
            row_frame,
            text=count_text,
            font=ctk.CTkFont(size=12),
            text_color=self.DOT_LIVE,
            anchor="e",
            width=100,
            fg_color="transparent",
            cursor="hand2",
        )
        count_label.pack(side="right", anchor="n", padx=(0, 8), pady=(6, 0))
        count_label.bind("<Button-1>", launch)
        count_label.bind("<Control-Button-1>", delete)
        count_label.bind("<Enter>", on_enter)
        count_label.bind("<Leave>", on_leave)

        # Channel name (and optional stream title below it)
        name_frame = ctk.CTkFrame(row_frame, fg_color="transparent", cursor="hand2")
        name_frame.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        name_frame.bind("<Button-1>", launch)
        name_frame.bind("<Control-Button-1>", delete)
        name_frame.bind("<Enter>", on_enter)
        name_frame.bind("<Leave>", on_leave)

        name_label = ctk.CTkLabel(
            name_frame,
            text=ch["name"],
            font=ctk.CTkFont(size=14),
            anchor="w",
            fg_color="transparent",
            cursor="hand2",
        )
        name_label.pack(fill="x", pady=(2, 0))
        name_label.bind("<Button-1>", launch)
        name_label.bind("<Control-Button-1>", delete)
        name_label.bind("<Enter>", on_enter)
        name_label.bind("<Leave>", on_leave)

        # Subtitle row: category (bold) + title — shown only when live
        subtitle_frame = ctk.CTkFrame(name_frame, fg_color="transparent", cursor="hand2")
        subtitle_frame.bind("<Button-1>", launch)
        subtitle_frame.bind("<Control-Button-1>", delete)
        subtitle_frame.bind("<Enter>", on_enter)
        subtitle_frame.bind("<Leave>", on_leave)
        if is_live and (category or title):
            subtitle_frame.pack(fill="x", pady=(0, 2))

        category_label = ctk.CTkLabel(
            subtitle_frame,
            text=category.upper() if is_live else "",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self._category_color(category) if is_live and category else "#cccccc",
            anchor="w",
            fg_color="transparent",
            cursor="hand2",
        )
        category_label.pack(side="left")
        category_label.bind("<Button-1>", launch)
        category_label.bind("<Control-Button-1>", delete)
        category_label.bind("<Enter>", on_enter)
        category_label.bind("<Leave>", on_leave)

        title_label = ctk.CTkLabel(
            subtitle_frame,
            text=title if is_live else "",
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            anchor="w",
            fg_color="transparent",
            cursor="hand2",
        )
        title_label.pack(side="left", padx=(6, 0))
        title_label.bind("<Button-1>", launch)
        title_label.bind("<Control-Button-1>", delete)
        title_label.bind("<Enter>", on_enter)
        title_label.bind("<Leave>", on_leave)

        self._row_widgets[ch["index"]] = {
            "frame": row_frame,
            "dot": dot,
            "count_label": count_label,
            "subtitle_frame": subtitle_frame,
            "category_label": category_label,
            "title_label": title_label,
        }

    # ── Add channel ───────────────────────────────────────────────────────────

    def _add_channel_from_entry(self, event=None) -> None:
        text = self.add_entry.get().strip()
        if not text:
            return

        parts = text.split(None, 1)
        login = parts[0].lower()
        name = parts[1] if len(parts) > 1 else login.upper()

        # Ignore duplicates
        if any(ch["login"] == login for ch in self.channels):
            self.add_entry.delete(0, "end")
            return

        ch = {"name": name, "url": f"https://www.twitch.tv/{login}", "login": login, "index": len(self.channels)}
        self.channels.append(ch)

        # Persist to channels.txt
        with open(CHANNELS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{login} {name}\n" if len(parts) > 1 else f"{login}\n")

        # Clear empty state label if present
        if self._empty_label:
            self._empty_label.destroy()
            self._empty_label = None

        self._add_channel_row(ch["index"], ch)
        self.add_entry.delete(0, "end")
        self._manual_refresh()

    # ── Delete channel ────────────────────────────────────────────────────────

    def _delete_channel(self, ch: dict) -> None:
        # Remove from UI
        widgets = self._row_widgets.pop(ch["index"], None)
        if widgets:
            widgets["frame"].destroy()

        # Remove from channel list
        self.channels = [c for c in self.channels if c["login"] != ch["login"]]

        # Rewrite channels.txt, dropping the matching line
        lines = CHANNELS_FILE.read_text(encoding="utf-8").splitlines()
        new_lines = [
            line for line in lines
            if not (line.strip() and not line.strip().startswith("#")
                    and line.strip().split(None, 1)[0].lower() == ch["login"])
        ]
        CHANNELS_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        # Show empty state if the list is now empty
        if not self.channels and not self._empty_label:
            self._empty_label = ctk.CTkLabel(
                self.scroll_frame,
                text="No channels found. Add one above.",
                font=ctk.CTkFont(size=13),
                text_color="#888888",
            )
            self._empty_label.pack(pady=40)

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
        full_line = f"[{name}] {line}\n"
        if re.search(r"advertisement", line, re.IGNORECASE):
            tag = "log_ad"
            match = re.search(r"(\d+)\s+seconds?", line, re.IGNORECASE)
            if match:
                self._start_ad_timer(int(match.group(1)))
        elif re.search(r"resuming stream output", line, re.IGNORECASE):
            tag = "log_resume"
            if self._ad_timer_job:
                self.after_cancel(self._ad_timer_job)
                self._ad_timer_job = None
            self.ad_timer_label.pack_forget()
        else:
            tag = None
        self.log_box._textbox.insert("end", full_line, (tag,) if tag else ())
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _category_color(self, category: str) -> str:
        low = category.lower()
        if any(kw in low for kw in self.category_keywords):
            return "#5dade2"  # light blue
        return "#cccccc"

    # ── Tooltip ───────────────────────────────────────────────────────────────

    def _attach_tooltip(self, widget, text: str) -> None:
        tip = [None]

        def show(e):
            tip[0] = tk.Toplevel(widget)
            tip[0].wm_overrideredirect(True)
            tip[0].wm_geometry(f"+{e.x_root + 12}+{e.y_root + 8}")
            tk.Label(tip[0], text=text, background="#333333", foreground="#ffffff",
                     font=("Segoe UI", 10), padx=6, pady=3, relief="flat").pack()

        def hide(e):
            if tip[0]:
                tip[0].destroy()
                tip[0] = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    # ── Ad break timer ────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_ad_time(seconds: int) -> str:
        return f"{seconds // 60:02}:{seconds % 60:02}"

    def _start_ad_timer(self, seconds: int) -> None:
        if self._ad_timer_job:
            self.after_cancel(self._ad_timer_job)
        self._ad_seconds_remaining = seconds
        self.ad_timer_label.configure(text=self._fmt_ad_time(seconds))
        self.ad_timer_label.pack(side="right", padx=(0, 12))
        self._ad_timer_job = self.after(1000, self._tick_ad_timer)

    def _tick_ad_timer(self) -> None:
        self._ad_seconds_remaining -= 1
        if self._ad_seconds_remaining <= 0:
            self.ad_timer_label.pack_forget()
            self._ad_timer_job = None
        else:
            self.ad_timer_label.configure(text=self._fmt_ad_time(self._ad_seconds_remaining))
            self._ad_timer_job = self.after(1000, self._tick_ad_timer)

    # ── Countdown bar ─────────────────────────────────────────────────────────

    def _reset_countdown(self) -> None:
        if self._countdown_job:
            self.after_cancel(self._countdown_job)
        self._countdown_remaining = self.COUNTDOWN_STEPS
        self.countdown_bar.set(0.0)
        self._countdown_job = self.after(self.COUNTDOWN_TICK_MS, self._tick_countdown)

    def _tick_countdown(self) -> None:
        self._countdown_remaining -= 1
        self.countdown_bar.set(1.0 - max(0.0, self._countdown_remaining / self.COUNTDOWN_STEPS))
        if self._countdown_remaining > 0:
            self._countdown_job = self.after(self.COUNTDOWN_TICK_MS, self._tick_countdown)
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

    def _apply_status(self, live: dict[str, dict]) -> None:
        if self.api_enabled:
            self._reset_countdown()

        # Sort live channels to the top, preserving original file order within each group
        self.channels.sort(key=lambda ch: (0 if ch["login"] in live else 1, ch["index"]))

        # Update widgets in-place — no destroy/recreate
        for ch in self.channels:
            widgets = self._row_widgets.get(ch["index"])
            if not widgets:
                continue
            is_live = bool(ch["login"] and ch["login"] in live)
            info = live.get(ch["login"], {}) if ch["login"] else {}
            count = info.get("viewers", 0)
            title = info.get("title", "")
            category = info.get("category", "")

            widgets["dot"].configure(
                text_color=self.DOT_LIVE if is_live else self.DOT_OFFLINE
            )
            widgets["count_label"].configure(
                text=_fmt_viewers(count) if is_live and count > 0 else ""
            )
            sf = widgets["subtitle_frame"]
            if is_live and (category or title):
                widgets["category_label"].configure(
                    text=category.upper(),
                    text_color=self._category_color(category) if category else "#cccccc",
                )
                widgets["title_label"].configure(text=title)
                sf.pack(fill="x", pady=(0, 2))
            else:
                sf.pack_forget()

        # Reorder rows without destroying them
        for ch in self.channels:
            widgets = self._row_widgets.get(ch["index"])
            if widgets:
                widgets["frame"].pack_forget()
        for ch in self.channels:
            widgets = self._row_widgets.get(ch["index"])
            if widgets:
                widgets["frame"].pack(fill="x", pady=1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    # Ensure channels.txt exists with a helpful template
    if not CHANNELS_FILE.exists():
        CHANNELS_FILE.write_text(
            "# streamfront channel list\n"
            "# One Twitch login per line, with an optional display name after a space\n"
            "# Lines starting with # are ignored\n\n"
            "# Examples:\n"
            "# xqc\n"
            "# goodtimeswithscar Scar\n",
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
