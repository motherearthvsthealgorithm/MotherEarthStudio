#!/bin/bash

clear

STUDIO="$HOME/Documents/MotherEarthStudio"
INPUT_DIR="$STUDIO/Input"
OUTPUT_DIR="$STUDIO/Output"
TEMPLATE_DIR="$STUDIO/Templates"

LENGTH="8"
SOURCE_LENGTH="7.2"
FADE_START="7.2"

mkdir -p "$INPUT_DIR" "$OUTPUT_DIR" "$TEMPLATE_DIR"

TITLE_FILE="$TEMPLATE_DIR/title.txt"
SUBTITLE_FILE="$TEMPLATE_DIR/subtitle.txt"

printf '%s\n' "Mother Earth vs. The Algorithm" > "$TITLE_FILE"
printf '%s\n' "I'm here to ask different questions." > "$SUBTITLE_FILE"

FONT="/System/Library/Fonts/HelveticaNeue.ttc"

if [ ! -f "$FONT" ]; then
    FONT="/System/Library/Fonts/Supplemental/Arial.ttf"
fi

echo "🌲 Mother Earth Studio v0.2"
echo ""
echo "This version creates an 8-second vertical video."
echo ""

read -r -p "Type the exact video filename from the Input folder: " VIDEO
read -r -p "Enter the starting second, or press Return to start at 0: " START

START="${START:-0}"

INPUT="$INPUT_DIR/$VIDEO"
BASENAME="${VIDEO%.*}"
OUTPUT="$OUTPUT_DIR/${BASENAME}_MotherEarth_v02.mp4"

if [ ! -f "$INPUT" ]; then
    echo ""
    echo "❌ Video not found."
    echo ""
    echo "I looked here:"
    echo "$INPUT"
    echo ""
    echo "Check the spelling, capitalization, and file extension."
    echo ""
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo ""
echo "🎬 Rendering your Mother Earth draft..."
echo "Please leave this window open."
echo ""

ffmpeg -y \
-ss "$START" \
-t "$SOURCE_LENGTH" \
-i "$INPUT" \
-filter_complex "
[0:v]
setpts=PTS/0.90,
scale=1080:1920:force_original_aspect_ratio=increase,
crop=1080:1920,
eq=contrast=0.97:saturation=0.98:brightness=0.01,
drawtext=fontfile='$FONT':textfile='$TITLE_FILE':reload=0:fontcolor=white@0.92:fontsize=58:x=(w-text_w)/2:y=h*0.42:alpha='if(lt(t,0.8),0,if(lt(t,2.0),(t-0.8)/1.2,if(lt(t,6.4),1,if(lt(t,7.2),(7.2-t)/0.8,0))))',
drawtext=fontfile='$FONT':textfile='$SUBTITLE_FILE':reload=0:fontcolor=white@0.88:fontsize=32:x=(w-text_w)/2:y=h*0.49:alpha='if(lt(t,2.0),0,if(lt(t,3.0),(t-2.0),if(lt(t,6.4),1,if(lt(t,7.2),(7.2-t)/0.8,0))))',
fade=t=out:st=7.2:d=0.8,
format=yuv420p
[v];
[0:a]
atempo=0.90,
afade=t=out:st=7.2:d=0.8
[a]
" \
-map "[v]" \
-map "[a]" \
-t "$LENGTH" \
-c:v libx264 \
-preset fast \
-crf 20 \
-c:a aac \
-b:a 192k \
-movflags +faststart \
"$OUTPUT"

STATUS=$?

echo ""

if [ "$STATUS" -eq 0 ]; then
    echo "✅ Finished!"
    echo ""
    echo "Your new video is here:"
    echo "$OUTPUT"
    echo ""
    open "$OUTPUT"
else
    echo "❌ The render did not finish."
    echo "Take a picture of the final error messages and send it here."
fi

echo ""
read -n 1 -s -r -p "Press any key to close..."
