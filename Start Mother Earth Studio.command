#!/bin/bash
set -e
cd "$(dirname "$0")"

# Prefer Homebrew's full FFmpeg build so burned captions work without a
# separate Terminal command. Intel and Apple Silicon locations are supported.
if [ -x "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg" ]; then
  export PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH"
  export MOTHER_EARTH_FFMPEG="/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
  export MOTHER_EARTH_FFPROBE="/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"
elif [ -x "/usr/local/opt/ffmpeg-full/bin/ffmpeg" ]; then
  export PATH="/usr/local/opt/ffmpeg-full/bin:$PATH"
  export MOTHER_EARTH_FFMPEG="/usr/local/opt/ffmpeg-full/bin/ffmpeg"
  export MOTHER_EARTH_FFPROBE="/usr/local/opt/ffmpeg-full/bin/ffprobe"
fi

if [ ! -d ".venv" ]; then
  echo "Creating Mother Earth Studio environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
if ! python -c "import whisper" >/dev/null 2>&1; then
  echo "Installing local caption tools. This may take several minutes the first time..."
  python -m pip install -r requirements.txt
fi

python app.py
