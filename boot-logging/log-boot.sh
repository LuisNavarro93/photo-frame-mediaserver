#!/bin/bash
LOGFILE="/home/portrait/Desktop/logs/schedule.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') - STARTUP - machine turned ON" >> "$LOGFILE"
chown portrait:portrait "$LOGFILE" 2>/dev/null
