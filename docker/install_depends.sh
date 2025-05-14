#!/bin/sh

set -e

apt-get -y update -qq
apt-get -y install gnupg2 ca-certificates
apt-get -y update -qq

apt-get -y --no-install-recommends install \
 python-is-python3 python3-pip gpp `echo ${EXTRA_PACKAGES}`

find /usr/lib -type f -name 'EXTERNALLY-MANAGED' -delete
