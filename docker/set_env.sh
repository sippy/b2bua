#!/bin/sh

set -e
set -x

platformopts() {
  local IMAGE_TAG="${BASE_IMAGE#*:}"
  local _OS_TAG="${IMAGE_TAG%%_*}"
  local OS_TAG="${_OS_TAG#*-}"

  case "${TARGETPLATFORM}" in
  linux/arm/v5)
    echo "RTPP_VERSION=production"
    echo "MM_INIT_DELAY=6"
    test "${OS_TAG}" != "debian" || echo "TEST_SET_MIGHTFAIL=early_cancel_lost100,early_cancel"
    ;;
  linux/arm/v7)
    echo "RTPP_VERSION=production"
    echo "OPENSSL_CONFIGURE_ARGS=linux-armv4"
    echo "MM_INIT_DELAY=6"
    test "${OS_TAG}" != "debian" || echo "TEST_SET_MIGHTFAIL=early_cancel_lost100"
    ;;
  linux/s390x)
    echo "RTPP_VERSION=production"
    echo "MM_INIT_DELAY=6"
    ;;
  linux/arm64)
    echo "QEMU_CPU=cortex-a53"
    echo "MM_INIT_DELAY=6"
    ;;
  linux/ppc64le)
    echo "MM_INIT_DELAY=6"
    ;;
  linux/riscv64)
    echo "MM_INIT_DELAY=6"
    echo "TEST_SET_MIGHTFAIL=early_cancel_lost100,early_cancel"
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
