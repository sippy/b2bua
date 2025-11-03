#!/bin/sh

set -e
set -x

platformopts() {
  case "${TARGETPLATFORM}" in
  linux/arm/v5)
    echo "RTPP_VERSION=production"
    ;;
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
  echo 'EXTRA_PACKAGES="build-essential libunwind-dev git python3-dev"'
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
