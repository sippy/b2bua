from threading import Lock
from typing import Type

from rtpsynth.RtpProc import RtpProc
from rtpsynth.RtpServer import RtpServer


_rtp_server_singleton = None
_rtp_server_refcount = 0
_rtp_server_lock = Lock()


def acquire_rtp_server(server_cls: Type[RtpServer]):
    global _rtp_server_singleton, _rtp_server_refcount
    with _rtp_server_lock:
        if _rtp_server_singleton is None:
            _rtp_server_singleton = server_cls()
        _rtp_server_refcount += 1
        return _rtp_server_singleton


def release_rtp_server(server):
    global _rtp_server_singleton, _rtp_server_refcount
    with _rtp_server_lock:
        if _rtp_server_singleton is None:
            return
        if server is not _rtp_server_singleton:
            return
        if _rtp_server_refcount > 0:
            _rtp_server_refcount -= 1
        if _rtp_server_refcount == 0:
            _rtp_server_singleton.shutdown()
            _rtp_server_singleton = None


_rtp_proc_singleton = None
_rtp_proc_refcount = 0
_rtp_proc_lock = Lock()


def acquire_rtp_proc():
    global _rtp_proc_singleton, _rtp_proc_refcount
    with _rtp_proc_lock:
        if _rtp_proc_singleton is None:
            _rtp_proc_singleton = RtpProc()
        _rtp_proc_refcount += 1
        return _rtp_proc_singleton


def release_rtp_proc(proc):
    global _rtp_proc_singleton, _rtp_proc_refcount
    with _rtp_proc_lock:
        if _rtp_proc_singleton is None:
            return
        if proc is not _rtp_proc_singleton:
            return
        if _rtp_proc_refcount > 0:
            _rtp_proc_refcount -= 1
        if _rtp_proc_refcount == 0:
            _rtp_proc_singleton.shutdown()
            _rtp_proc_singleton = None
