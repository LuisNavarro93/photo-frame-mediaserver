#!/bin/bash

xset s off
xset -dpms
xset s noblank

mpv --fullscreen \
    --loop-playlist=inf \
    --image-display-duration=6 \
    --no-osc \
    --shuffle \
    ~/Pictures/
