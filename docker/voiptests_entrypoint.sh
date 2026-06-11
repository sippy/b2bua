#!/bin/sh

set -e

cd /tmp/dist/voiptests
rm -rf test.logs

export RTPPC_TYPE="${RTPPC_TYPE:-unix}"
eval "`${SET_ENV}`"
TEST_RES="ok"
sh -x ./test_run.sh || TEST_RES="fail"
mkdir -p "test.logs/${RTPPC_TYPE}"
for f in alice.log bob.log rtpproxy.log b2bua.log rtpproxy.rout.diff.txt
do
  mv "${f}" "test.logs/${RTPPC_TYPE}" || true
done
test "${TEST_RES}" = "ok"
