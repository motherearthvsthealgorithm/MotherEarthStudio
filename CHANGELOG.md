# Changelog

## 0.9.3

- Fixed portable caption rendering on Homebrew/macOS FFmpeg by removing `-filter_script:v`.
- Added direct FFmpeg `-vf` drawtext graphs.
- Added macOS font-file discovery.
- Added per-export build logs.
- Added caption-filter initialization verification.
- Corrected success messaging so captionless exports are never described as captioned.

## 0.9.2

- Added portable drawtext caption renderer and `.srt` sidecars.

## 0.9.5 — Story-First Foundation
- Loop background footage to narration duration plus a 1.5-second visual tail.
- Continue and fade music through the tail.
- Add story-first emphasis caption generation.
- Add caption review workflow.
- Add composition-aware variable caption placement.
- Adopt calmer Mother Earth-aligned typography.
