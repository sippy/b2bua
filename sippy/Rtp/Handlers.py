from typing import Type, Any

from .OutputWorker import RTPOutputWorker
from .Ingest import RTPInStream
from sippy.Udp_server import Udp_server, Udp_server_opts
from rtpsynth.RtpServer import RtpServer


class RTPHandlers():
    writer_cls: Type[Any] = RTPOutputWorker
    rtp_instream_cls: Type[Any] = RTPInStream
    rtp_server_cls: Type[Any] = RtpServer
    udp_server_cls: Type[Any] = Udp_server
    udp_server_opts_cls: Type[Any] = Udp_server_opts
