# Mother Earth Studio 0.9.3

Mother Earth Studio is a story-first documentary creator for *Mother Earth vs. The Algorithm*.

## Start on macOS

Control-click `Start Mother Earth Studio.command`, choose **Open**, and approve the one-time macOS security prompt.

## Creator path

1. Enter an episode title.
2. Paste or load the approved script when available.
3. Choose forest footage and narration.
4. Optionally choose music.
5. Generate or select a standard `.srt` caption file.
6. Keep **Burn captions into video when supported** checked.
7. Build the episode.

## Caption results

Version 0.9.3 uses an explicit FFmpeg caption filter and verifies that FFmpeg initialized it. Every export receives a matching `.build.log` describing what happened.

Studio will report one of these outcomes:

- **Captions visibly burned**
- **MP4 created without burned captions**
- **Caption build failed**

A matching `.srt` is retained beside the finished MP4 whenever captions were supplied.
