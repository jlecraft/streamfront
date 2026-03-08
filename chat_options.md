# Twitch Chat Integration Options

## Option 1 — Twitch IRC over WebSocket (pure Python)
- Connect anonymously to `wss://irc-ws.chat.twitch.tv` using the `websockets` library — no OAuth needed for read-only
- Parse incoming IRC messages and display them in a `CTkTextbox` panel
- **Pros:** lightweight, fully styled to match the app, no browser dependency
- **Cons:** requires building message parsing, reconnect logic, rate-limit handling
- **New dependency:** `websockets`

## Option 2 — Embedded browser via `tkinterweb`
- `tkinterweb` is a pip-installable tkinter widget that renders HTML
- Load Twitch's official chat embed: `https://www.twitch.tv/embed/{channel}/chat?parent=localhost`
- **Pros:** official Twitch chat UI, no message parsing needed
- **Cons:** `tkinterweb` has limited CSS support — Twitch's chat page may not render well
- **New dependency:** `tkinterweb`

## Option 3 — `pywebview` pop-out window
- `pywebview` opens a native OS webview window (Edge/WebKit) pointed at the Twitch chat embed URL
- **Pros:** full, pixel-perfect Twitch chat in a proper browser engine; simple to implement
- **Cons:** chat opens in a separate window rather than inside the app
- **New dependency:** `pywebview`

## Design Questions to Resolve Before Implementing

1. **Chat location** — Inside the main window as a panel/sidebar, or a separate pop-out window?
2. **Approach** — Twitch IRC (pure Python, custom styled) or pywebview (official Twitch UI)?
3. **Chat trigger** — How is a stream selected for chat?
   - Single click opens chat (stream launch moves to double-click)
   - A dedicated chat button per row
   - Chat opens automatically when a stream is launched
