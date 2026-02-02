from typing import Optional

from sippy.Network_server import RTP_port_allocator

class RTPConf():
    palloc: RTP_port_allocator
    def __init__(self, min_port=None, max_port=None):
        self.palloc = RTP_port_allocator(min_port, max_port)
