# Changelog

## Unreleased

### Added
- Stream title displayed below the channel name when a stream is live
- Output log now highlights lines containing "advertisement" in red and "resuming stream output" in green (case-insensitive)

### Changed
- Viewer count is now green to match the live status indicator, making it easier to distinguish from the stream title
- Viewer count is top-aligned with the channel name rather than centered in the row
- Status refreshes no longer cause a full UI redraw — channel rows are updated in-place and reordered without being destroyed, eliminating the visible flash
