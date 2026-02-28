# TwitchLauncher — Installation Guide

## Requirements

- Windows 10 or 11
- [Python 3.10+](https://www.python.org/downloads/)
- [VLC media player](https://www.videolan.org/vlc/)
- [Streamlink](https://streamlink.github.io/install.html)

---

## Step 1 — Install Python

1. Go to https://www.python.org/downloads/ and download the latest Python 3 installer
2. Run the installer
3. **Important:** Check the box that says **"Add Python to PATH"** before clicking Install
4. Click **Install Now**
5. Verify the install by opening Command Prompt and running:
   ```
   python --version
   ```
   You should see something like `Python 3.12.x`

---

## Step 2 — Install VLC

1. Go to https://www.videolan.org/vlc/ and download VLC for Windows
2. Run the installer and follow the prompts
3. VLC installs to `C:\Program Files\VideoLAN\VLC\` by default — note this path for later

---

## Step 3 — Install Streamlink

1. Go to https://streamlink.github.io/install.html
2. Download the **Windows installer** (the `.exe` file under the Windows section)
3. Run the installer and follow the prompts
4. Verify the install by opening a new Command Prompt and running:
   ```
   streamlink --version
   ```
   You should see something like `streamlink 8.x.x`

---

## Step 4 — Download TwitchLauncher

**Option A — Clone with Git** (if you have Git installed):
```
git clone https://github.com/jlecraft/TwitchLauncher.git C:\Projects\TwitchLauncher
```

**Option B — Download ZIP:**
1. Go to https://github.com/jlecraft/TwitchLauncher
2. Click the green **Code** button → **Download ZIP**
3. Extract the ZIP to `C:\Projects\TwitchLauncher\`

---

## Step 5 — Install Python Dependencies

Open Command Prompt, navigate to the project folder, and run:

```
cd C:\Projects\TwitchLauncher
pip install -r requirements.txt
```

---

## Step 6 — Configure the App

Create a file called `config.ini` in `C:\Projects\TwitchLauncher\` with the following content:

```ini
[streamlink]
quality = best
player = C:\Program Files\VideoLAN\VLC\vlc.exe

[twitch_api]
client_id =
client_secret =
```

> **Note:** If you installed VLC to a different location, update the `player` path accordingly.
> The `client_id` and `client_secret` fields are optional — see Step 7.

---

## Step 7 — Set Up Twitch API Credentials (Optional)

This step enables **live status indicators** and **viewer counts**. The app works without it,
but all status dots will remain gray.

1. Go to https://dev.twitch.tv/console and log in with your Twitch account
2. You must have **Two-Factor Authentication** enabled on your Twitch account to access the console
   - Enable it at: Twitch → Settings → Security and Privacy → Set Up Two-Factor Authentication
3. Click **Register Your Application**
4. Fill in the form:
   - **Name:** anything you like (e.g. `StreamLaunch`) — Twitch does not allow "Twitch" in the name
   - **OAuth Redirect URL:** `http://localhost`
   - **Category:** Application Integration
   - **Client Type:** Confidential
5. Click **Create**
6. Copy the **Client ID** shown on the page
7. Click **New Secret** to generate a **Client Secret** and copy it
8. Open `config.ini` and paste both values:
   ```ini
   [twitch_api]
   client_id = your_client_id_here
   client_secret = your_client_secret_here
   ```

---

## Step 8 — Add Your Channels

Edit `C:\Projects\TwitchLauncher\channels.txt` and add channels in this format:

```
Display Name | https://twitch.tv/channelname
```

Lines starting with `#` are treated as comments and ignored. Example:

```
# My favourite streamers
Grian | https://twitch.tv/grian
Xisumavoid | https://twitch.tv/xisuma
```

---

## Step 9 — Run the App

```
cd C:\Projects\TwitchLauncher
python main.py
```

---

## Step 10 — Create a Desktop Shortcut (Optional)

1. Open `C:\Projects\TwitchLauncher\` in File Explorer
2. Right-click `launch.bat` → **Send to** → **Desktop (create shortcut)**
3. Double-clicking the shortcut will launch TwitchLauncher without a console window

To add the custom icon to the shortcut:
1. Right-click the desktop shortcut → **Properties**
2. Click **Change Icon**
3. Browse to `C:\Projects\TwitchLauncher\icon.ico`
4. Click **OK**

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `python` not found | Re-run the Python installer and check "Add Python to PATH" |
| `streamlink` not found | Re-run the Streamlink installer; open a new Command Prompt after installing |
| Clicking a channel does nothing | Check that the `player` path in `config.ini` points to `vlc.exe` |
| All dots are gray | Twitch API credentials are missing or incorrect — see Step 7 |
| Stream won't open | Make sure the channel is live; check the Output log at the bottom of the app for error details |
