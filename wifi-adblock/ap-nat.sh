#!/bin/bash
iptables -t nat -C POSTROUTING -o wlp3s0 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -o wlp3s0 -j MASQUERADE
iptables -C FORWARD -i wlp3s0 -o ap0 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -A FORWARD -i wlp3s0 -o ap0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -C FORWARD -i ap0 -o wlp3s0 -j ACCEPT 2>/dev/null || iptables -A FORWARD -i ap0 -o wlp3s0 -j ACCEPT
