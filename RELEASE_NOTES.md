# Mother Earth Studio 0.9.3 — Caption Verification Release

This release fixes the macOS caption-rendering path discovered in 0.9.2.

## Changes

- Replaces `-filter_script:v` with an explicit `-vf` caption filter graph.
- Uses a real macOS font file when available.
- Writes a `.build.log` beside every completed MP4.
- Refuses to report success when FFmpeg does not confirm that the requested caption filter initialized.
- Uses explicit creator-facing results: captions burned, MP4 without burned captions, or caption build failed.
- Keeps the matching `.srt` beside the exported MP4.

## Continuity rule

If caption rendering is unavailable, Studio may still create a post-ready MP4 and sidecar `.srt`. If a renderer is requested but cannot be verified, the caption build fails rather than silently presenting a captionless file as captioned.
