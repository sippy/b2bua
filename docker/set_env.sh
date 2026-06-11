#!/bin/sh

set -e
set -x

fexport() {
  echo "export ${1}"
}

platformopts() {
  local IMAGE_TAG="${BASE_IMAGE#*:}"
  local _OS_TAG="${IMAGE_TAG%%_*}"
  local OS_TAG="${_OS_TAG#*-}"

  case "${TARGETPLATFORM}" in
  linux/arm/v5)
    fexport RTPP_VERSION=production
    fexport MM_WAITREADY=6
    fexport MM_INIT_DELAY=8
    fexport TEST_SET_MIGHTFAIL=early_cancel_lost100,early_cancel
    ;;
  linux/arm/v7)
    fexport RTPP_VERSION=production
    fexport OPENSSL_CONFIGURE_ARGS=linux-armv4
    fexport MM_INIT_DELAY=6
    fexport TEST_SET_MIGHTFAIL=early_cancel_lost100,early_cancel
    ;;
  linux/s390x)
    fexport RTPP_VERSION=production
    fexport MM_INIT_DELAY=6
    fexport TEST_SET_MIGHTFAIL=early_cancel_lost100,early_cancel
    ;;
  linux/arm64)
    fexport QEMU_CPU=cortex-a72
    fexport MM_INIT_DELAY=6
    fexport TEST_SET_MIGHTFAIL=early_cancel_lost100,early_cancel
    ;;
  linux/ppc64le)
    fexport MM_INIT_DELAY=6
    fexport TEST_SET_MIGHTFAIL=early_cancel_lost100,early_cancel
    ;;
  linux/riscv64)
    fexport TEST_SET_MIGHTFAIL=early_cancel_lost100,early_cancel
    case "${OS_TAG}" in
    ubuntu)
      fexport 'CFLAGS_opt="-O1 -g3 -pipe -flto"'
      fexport MM_WAITREADY=10
      fexport MM_INIT_DELAY=12
      ;;
    *)
      fexport MM_INIT_DELAY=6
      ;;
    esac
    ;;
  esac
  fexport 'EXTRA_PACKAGES="build-essential libunwind-dev git python3-dev cmake ninja-build patchelf"'
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
