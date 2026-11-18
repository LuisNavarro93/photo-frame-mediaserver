#!/bin/bash
cd /home/portrait/Documents/photo-frame-mediaserver/webapp
export DJANGO_SETTINGS_MODULE=frame_web.settings
LOGFILE=/home/portrait/Desktop/logs/webapp.log

while true; do
    python3 manage.py runserver 0.0.0.0:8800 --noreload >> "$LOGFILE" 2>&1
done
