# streamfront — Installation Guide

## Requirements

- Windows 10 or 11
- [Python 3.10+](https://www.python.org/downloads/)
- [Streamlink](https://streamlink.github.io/install.html)
- A media player (e.g. [VLC](https://www.videolan.org/vlc/)) — optional, but required to open streams

---

## Step 1 — Install Python

1. Go to https://www.python.org/downloads/ and download the latest Python 3 installer
2. Run the installer
3. **Important:** Check the box that says **"Add Python to PATH"** before clicking Install
4. Click **Install Now**
5. Verify by opening Command Prompt and running:
   ```
   python --version
   ```
   You should see something like `Python 3.12.x`

---

## Step 2 — Install Streamlink

1. Go to https://streamlink.github.io/install.html
2. Download the **Windows installer** (the `.exe` file under the Windows section)
3. Run the installer and follow the prompts
4. Verify by opening a new Command Prompt and running:
   ```
   streamlink --version
   ```
   You should see something like `streamlink 8.x.x`

---

## Step 3 — Download streamfront

**Option A — Clone with Git** (if you have Git installed):
```
git clone https://github.com/jlecraft/streamfront.git C:\Projects\streamfront
```

**Option B — Download ZIP:**
1. Go to https://github.com/jlecraft/streamfront
2. Click the green **Code** button → **Download ZIP**
3. Extract the ZIP to `C:\Projects\streamfront\`

---

## Step 4 — Install Python Dependencies

Open Command Prompt, navigate to the project folder, and run:

```
cd C:\Projects\streamfront
pip install -r requirements.txt
```

---

## Step 5 — Initialize

Run the included setup script:

```
cd C:\Projects\streamfront
python init.py
```

This will:
- Generate `launch.bat` (launches the app without a console window)
- Create a `channels.txt` file for your channel list
- Create a `category.txt` file for category highlighting keywords
- Create a documented `config.ini` for your settings
- Create a `streamfront` shortcut on your Desktop with the custom icon

---

## Step 6 — Configure the App

Open `config.ini` in a text editor. All settings are optional:

```ini
[player]
# Full path to your media player executable.
# path = C:\Program Files\VideoLAN\VLC\vlc.exe

[twitch]
# Twitch API credentials — enables live status, viewer counts, and stream titles.
# client_id = your_client_id_here
# client_secret = your_client_secret_here
```

Uncomment and fill in the values you want to use.

> Without a `player` path, clicking a channel will still invoke streamlink but won't open a player window.
> Without Twitch credentials, all status dots remain gray.

---

## Step 7 — Set Up Twitch API Credentials (Optional)

This enables live status indicators, viewer counts, stream titles, and category highlighting.

1. Go to https://dev.twitch.tv/console and log in with your Twitch account
2. You must have **Two-Factor Authentication** enabled on your Twitch account
   - Enable it at: Twitch → Settings → Security and Privacy → Set Up Two-Factor Authentication
3. Click **Register Your Application**
4. Fill in the form:
   - **Name:** anything you like (e.g. `streamfront`) — Twitch does not allow "Twitch" in the name
   - **OAuth Redirect URL:** `http://localhost`
   - **Category:** Application Integration
   - **Client Type:** Confidential
5. Click **Create**
6. Copy the **Client ID** shown on the page
7. Click **New Secret** to generate a **Client Secret** and copy it
8. Open `config.ini` and paste both values under `[twitch]`

---

## Step 8 — Add Your Channels

Edit `channels.txt` — one Twitch login per line, with an optional display name after a space:

```
# Lines starting with # are ignored
grian
goodtimeswithscar Scar
impulsesv Impulse
```

If no display name is given, the login is shown in ALL CAPS. You can also add and remove channels directly from the app's UI.

---

## Step 9 — Launch the App

Double-click the **streamfront** shortcut on your Desktop, or run:

```
python main.py
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `python` not found | Re-run the Python installer and check "Add Python to PATH" |
| `streamlink` not found | Re-run the Streamlink installer; open a new Command Prompt after installing |
| Clicking a channel does nothing | Check that the `player` path in `config.ini` is correct |
| All dots are gray | Twitch API credentials are missing or incorrect — see Step 7 |
| Stream won't open | Make sure the channel is live; check the Output log at the bottom of the app |
