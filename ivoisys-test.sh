#!/bin/sh

sudo python2.6 b2bua_radius.py --digest_auth_only=on \
  -A 0 --rtp_proxy_clients="/var/run/rtpproxy.sock" --sip_proxy=202.85.245.137 --nat_traversal=on
