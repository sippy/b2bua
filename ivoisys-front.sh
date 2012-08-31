#!/bin/sh

export SIPLOG_BEND=syslog

python2.6 b2bua_radius.py --digest_auth=on --accept_ips=202.85.243.105,202.85.245.137 \
  -A 0 --sip_proxy=202.85.245.137 \
  --nat_traversal=on --pass_headers=Remote-Party-ID,Allow,Supported \
  --rtp_proxy_clients="/var/run/rtpproxy.sock"
