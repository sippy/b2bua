class GenCodec():
    srate:int = 8000 # sample rate
    out_srate:int    # sample rate (output)
    crate:int = 8000 # clock rate
    ptype:int        # payload type
    ename:str        # encoding name

    def __init__(self):
        assert self.ptype is not None and self.ename is not None
        self.out_srate = self.srate

    @classmethod
    def rtpmap(cls):
        assert all(hasattr(cls, attr) for attr in ('ptype', 'ename'))
        return f'rtpmap:{cls.ptype} {cls.ename}/{cls.crate}'

    def e2t(self, frames:int) -> float:
        return frames / self.srate
