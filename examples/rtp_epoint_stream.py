#!/usr/bin/env python3
import argparse
import os
import sys
import threading

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
SCRIPT_DIR = os.path.dirname(__file__)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from rtp_epoint_common import FeedingOutputWorker, FeedingRTPParams, WaveChunker, parse_target, codec_from_name
from sippy.Rtp.Handlers import RTPHandlers
from sippy.Rtp.Conf import RTPConf
from sippy.Rtp.EPoint import RTPEPoint


def main():
    parser = argparse.ArgumentParser(description='Stream WAV via RTP/G711 using RTPEPoint')
    parser.add_argument('target', help='host:port destination for RTP')
    parser.add_argument('wav', help='path to WAV file')
    parser.add_argument('--codec', default='g711', help='g711 or g722')
    parser.add_argument('--ptime', type=int, default=20, help='RTP ptime in ms')
    parser.add_argument('--chunk-ms', type=int, default=None, help='chunk size in ms (default=ptime * 10)')
    args = parser.parse_args()

    host, port = parse_target(args.target)

    handlers = RTPHandlers()
    handlers.writer_cls = FeedingOutputWorker

    chunk_ms = args.chunk_ms or args.ptime * 10
    chunker = WaveChunker(args.wav, 1)
    frames_per_chunk = max(1, int(chunker.rate * (chunk_ms / 1000.0)))
    chunker.frames_per_chunk = frames_per_chunk
    done = threading.Event()

    def on_drain(writer):
        if done.is_set():
            return
        chunk = chunker.next_chunk()
        if chunk is None:
            done.set()
            writer.end()
            return
        writer.soundout(chunk)

    rtp_params = FeedingRTPParams((host, port), on_drain=on_drain, out_ptime=args.ptime)
    rtp_params.codec = codec_from_name(args.codec)

    rc = RTPConf()

    def audio_in(_chunk):
        pass

    ep = RTPEPoint(rc, rtp_params, audio_in, handlers=handlers)

    try:
        done.wait()
    except KeyboardInterrupt:
        ep.writer.end()
    finally:
        ep.shutdown()
        chunker.close()


if __name__ == '__main__':
    main()
