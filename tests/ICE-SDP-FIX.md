# ICE SDP scope fixes

Affected inspected snapshot: 93ab85f46c965ab89416e2b74db9803e805f2a9b.
RFC 8839 section 5.3 makes ice-lite session-level only:
https://www.rfc-editor.org/rfc/rfc8839#section-5.3

The previous finalizer placed it in the media section; Chromium dropped it from
its parsed remote SDP during the Go port's browser test. Emit it at session level,
deduplicate repeat finalizers and remove it during de-ICE. Also remove exact-name
attributes at BOTH levels when an inherited duplicate exists. The old helper
removed a section match and skipped the same name at session scope.

Reproducer/regression (Docker only):
`docker run --rm -v "$PWD":/src -w /src python:3.12-slim python -m unittest tests.test_IceSdpScope`

Two tests pass after the fix. Other Python integration behavior has not been
revalidated. Go's corresponding fixes were verified with real browser calls.
