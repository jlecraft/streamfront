# streamfront

A Python GUI front-end for [streamlink](https://streamlink.github.io) that lets you launch streams with a single click.

## Features

- One-click stream launching via streamlink and VLC
- Live status indicators — green dot when a channel is streaming
- Viewer counts displayed next to live channels
- Live channels automatically sorted to the top of the list
- Auto-refreshes every 60 seconds with a visual countdown bar
- Row hover highlighting for easy navigation
- Streamlink output log at the bottom of the window
- Channel list loaded from a plain text file — easy to edit
- Desktop shortcut support via `launch.bat`

## Requirements

- Python 3.10+
- [Streamlink](https://streamlink.github.io/install.html)
- [VLC media player](https://www.videolan.org/vlc/)

## Quick Start

See **[install.md](install.md)** for full step-by-step setup instructions.

```
pip install -r requirements.txt
python main.py
```

## Channel List

Edit `channels.txt` to add your channels:

```
# Format: Display Name | URL
Grian | https://twitch.tv/grian
Xisumavoid | https://twitch.tv/xisuma
```

## Configuration

Edit `config.ini` to set your player path, stream quality, and optional Twitch API credentials for live status:

```ini
[streamlink]
quality = best
player = C:\Program Files\VideoLAN\VLC\vlc.exe

[twitch_api]
client_id = your_client_id
client_secret = your_client_secret
```

Twitch API credentials are free — see Step 7 of [install.md](install.md) for setup instructions.
