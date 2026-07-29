#!/bin/bash
export DISPLAY=:0
export XAUTHORITY=/home/portrait/.Xauthority

xset s off
xset -dpms
xset s noblank

PLAYLIST=/tmp/slideshow_playlist.txt
MEDIA_DIR=~/Pictures
LOGFILE=/home/portrait/Desktop/logs/schedule.log
INPUT_CONF=/home/portrait/.config/autostart/slideshow-input.conf

while true; do
    find "$MEDIA_DIR" -type f -not -name '.*' | shuf > "$PLAYLIST"

    mpv --fullscreen \
        --vo=x11 \
        --no-osc \
        --image-display-duration=6 \
        --input-conf="$INPUT_CONF" \
        --playlist="$PLAYLIST" 2>&1 | \
    stdbuf -oL grep --line-buffered -iE '^Playing:|error|fail|warning|cannot|unsupported|invalid' | \
    while IFS= read -r line; do
        if [[ "$line" == Playing:* ]]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') - SLIDESHOW - ${line#Playing: }" >> "$LOGFILE"
        else
            echo "$(date '+%Y-%m-%d %H:%M:%S') - SLIDESHOW-ERROR - $line" >> "$LOGFILE"
        fi
    done
done
