#!/bin/sh

set -e

platformopts() {
  case "${TARGETPLATFORM}" in
  linux/s390x | linux/arm/v7)
    echo "RTPP_VERSION=production"
    ;;
  linux/arm64)
    echo "QEMU_CPU=cortex-a53"
    ;;
  esac
  if [ "${TARGETPLATFORM}" != "linux/amd64" -a "${TARGETPLATFORM}" != "linux/arm64" ]
  then
    echo "EXTRA_PACKAGES=build-essential"
  fi

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
