# Changelog

## Unreleased

### Added
- Stream title displayed below the channel name when a stream is live
- Stream category (e.g. "MINECRAFT", "JUST CHATTING") shown in bold caps to the left of the title when live
- `category.txt` — add keywords (one per line) to highlight matching categories in light blue
- Output log highlights lines containing "advertisement" in red and "resuming stream output" in green (case-insensitive)
- Ad break timer in the header: auto-starts from the detected duration when an advertisement is logged, counts down in MM:SS, and clears automatically when the stream resumes. Hover for tooltip.
- Text entry field at the top of the window — type a Twitch login (optionally followed by a display name) and press Enter to add a streamer. Saves to `channels.txt` and refreshes live status immediately.
- Ctrl+click any channel row to instantly remove that streamer from the UI and `channels.txt`
- Optional display names in `channels.txt` — e.g. `goodtimeswithscar Scar` shows as "Scar" in the UI; login-only entries are shown in all caps

### Changed
- Viewer count is now green to match the live status indicator, making it easier to distinguish from the stream title
- Viewer count is top-aligned with the channel name rather than centered in the row
- Status refreshes no longer cause a full UI redraw — channel rows are updated in-place and reordered without being destroyed, eliminating the visible flash
- `channels.txt` format simplified to Twitch login names (URL is auto-generated); display name is optional
