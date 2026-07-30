#!/bin/bash
set -e
if ! ip link show ap0 &>/dev/null; then
    iw dev wlp3s0 interface add ap0 type __ap
fi
ip addr replace 192.168.50.1/24 dev ap0
ip link set ap0 up
