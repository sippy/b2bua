#!/bin/sh

sudo python2.6 b2bua_radius.py --digest_auth=off --accept_ips=202.85.245.137 \
  -A 0 -s 202.85.243.19 --auth_enable=off \
  --pass_headers=Remote-Party-ID,Allow,Supported
