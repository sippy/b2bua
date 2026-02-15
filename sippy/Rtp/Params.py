from functools import lru_cache
from ipaddress import ip_address
from typing import Optional, Tuple, Type, Union
from socket import AF_INET, AF_INET6

from sippy.misc import local4remote

from .Codecs.G711 import G711Codec
from .Codecs.G722 import G722Codec


@lru_cache(maxsize=256)
def canonicalize_rtp_host(host: str) -> str:
    if host.startswith('[') and host.endswith(']'):
        host = host[1:-1]
    try:
        return str(ip_address(host))
    except ValueError:
        return host


def canonicalize_rtp_target(rtp_target: Optional[Tuple[str, int]]) -> Optional[Tuple[str, int]]:
    if rtp_target is None:
        return None
    host, port = rtp_target
    assert isinstance(host, str)
    return (canonicalize_rtp_host(host), int(port))


def canonicalize_rtp_address(address) -> Optional[Tuple[str, int]]:
    if not isinstance(address, tuple) or len(address) < 2:
        return None
    host, port = address[:2]
    if not isinstance(host, str):
        return None
    return (canonicalize_rtp_host(host), int(port))


class RTPParams():
    _rtp_target: Optional[Tuple[str, int]]
    _rtp_proto: str
    rtp_laddr: str
    rtp_lport: int = 0
    out_ptime: int
    out_sr: int
    default_rtp_proto: str = 'IP4'
    default_ptime: int = 20
    default_sr: int = 16000
    codec: Type[Union[G711Codec, G722Codec]]

    def __init__(self, rtp_target:Optional[Tuple[str, int]], out_ptime:int=default_ptime,
                 out_sr:int=default_sr, rtp_proto:str=default_rtp_proto):
        self._rtp_target = None
        self._rtp_proto = self.default_rtp_proto
        self.rtp_laddr = '0.0.0.0'
        self.rtp_proto = rtp_proto
        self.rtp_target = rtp_target
        self.out_ptime = out_ptime
        self.out_sr = out_sr

    @property
    def rtp_target(self) -> Optional[Tuple[str, int]]:
        return self._rtp_target

    @rtp_target.setter
    def rtp_target(self, rtp_target: Optional[Tuple[str, int]]):
        assert rtp_target is None or (isinstance(rtp_target, tuple) and len(rtp_target) == 2)
        # Fast path for common "set to current value" updates.
        if rtp_target == self._rtp_target:
            return
        new_rtp_target = canonicalize_rtp_target(rtp_target)
        if new_rtp_target == self._rtp_target:
            return
        self._rtp_target = new_rtp_target
        self.rtp_laddr = self._get_laddr()

    @property
    def rtp_proto(self) -> str:
        return self._rtp_proto

    @rtp_proto.setter
    def rtp_proto(self, rtp_proto: str):
        assert isinstance(rtp_proto, str)
        rtp_proto = rtp_proto.upper()
        assert rtp_proto in ('IP4', 'IP6')
        if rtp_proto == self._rtp_proto:
            return
        self._rtp_proto = rtp_proto
        self.rtp_laddr = self._get_laddr()

    @property
    def rtp_family(self):
        return AF_INET if self.rtp_proto == 'IP4' else AF_INET6

    def _get_laddr(self):
        af = self.rtp_family
        target = self.rtp_target
        if target is None:
            rtp_laddr = '0.0.0.0' if af == AF_INET else '::'
        else:
            rtp_laddr = local4remote(target[0], family=af)
            if af == AF_INET6:
                rtp_laddr = rtp_laddr[1:-1]
        return rtp_laddr
