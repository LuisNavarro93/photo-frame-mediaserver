#!/bin/bash
export DISPLAY=:0
export XAUTHORITY=/home/portrait/.Xauthority

xset s off
xset -dpms
xset s noblank

PLAYLIST=/tmp/slideshow_playlist.txt
MEDIA_DIR=~/Pictures

while true; do
    find "$MEDIA_DIR" -type f -not -name '.*' | shuf > "$PLAYLIST"

    mpv --fullscreen \
        --vo=x11 \
        --no-osc \
        --image-display-duration=6 \
        --playlist="$PLAYLIST"
done
