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
