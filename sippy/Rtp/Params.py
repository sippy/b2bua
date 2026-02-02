from typing import Optional, Tuple, Type, Union

from .Codecs.G711 import G711Codec
from .Codecs.G722 import G722Codec

class RTPParams():
    rtp_target: Optional[Tuple[str, int]]
    out_ptime: int
    out_sr: int
    default_ptime: int = 20
    default_sr: int = 16000
    codec: Type[Union[G711Codec, G722Codec]]
    def __init__(self, rtp_target:Optional[Tuple[str, int]], out_ptime:int=default_ptime,
                 out_sr:int=default_sr):
        assert rtp_target is None or (isinstance(rtp_target, tuple) and len(rtp_target) == 2)
        self.rtp_target = rtp_target
        self.out_ptime = out_ptime
        self.out_sr = out_sr
