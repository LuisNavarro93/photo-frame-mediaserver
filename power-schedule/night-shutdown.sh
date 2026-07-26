#!/bin/bash
# Figure out tomorrow's day of week: 1=Mon ... 7=Sun
LOGFILE="/home/portrait/Desktop/logs/schedule.log"

TOMORROW_DOW=$(date -d "tomorrow" +%u)

if [ "$TOMORROW_DOW" -ge 1 ] && [ "$TOMORROW_DOW" -le 4 ]; then
    # Tomorrow is Mon-Thu -> wake at 5pm
    WAKE_TIME=$(date -d "tomorrow 17:00:00" +%s)
else
    # Tomorrow is Fri-Sun -> wake at 9am
    WAKE_TIME=$(date -d "tomorrow 09:00:00" +%s)
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - SHUTDOWN - turning off now; scheduled wake at $(date -d @"$WAKE_TIME" '+%Y-%m-%d %H:%M:%S')" >> "$LOGFILE"
chown portrait:portrait "$LOGFILE" 2>/dev/null

/usr/sbin/rtcwake -m off -t "$WAKE_TIME"
