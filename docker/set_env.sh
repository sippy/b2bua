#!/bin/sh

set -e
set -x

platformopts() {
  case "${TARGETPLATFORM}" in
  linux/arm/v7)
    echo "RTPP_VERSION=production"
    echo "OPENSSL_CONFIGURE_ARGS=linux-armv4"
    ;;
  linux/s390x)
    echo "RTPP_VERSION=production"
    ;;
  linux/arm64)
    echo "QEMU_CPU=cortex-a53"
    ;;
  esac
#  if [ "${TARGETPLATFORM}" != "linux/amd64" -a "${TARGETPLATFORM}" != "linux/arm64" ]
#  then
    echo 'EXTRA_PACKAGES="build-essential git python3-dev"'
#  fi

}

case "${1}" in
platformopts)
  shift
  platformopts "${@}"
  ;;
*)
  echo "usage: `basename "${0}"` platformopts [opts]" 2>&1
  exit 1
  ;;
esac
