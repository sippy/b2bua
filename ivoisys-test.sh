#!/bin/sh

sudo python2.6 b2bua_radius.py -f -u -s 'pennytel.com;op=202.85.245.137;auth=8889203691:sobomax123' \
  -A 0 --rtp_proxy_clients="/var/run/rtpproxy.sock" --sip_proxy=202.85.245.137 --nat_traversal=on
