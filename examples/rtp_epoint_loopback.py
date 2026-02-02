#!/usr/bin/env python3
import argparse
import os
import sys
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
SCRIPT_DIR = os.path.dirname(__file__)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from rtp_epoint_common import FeedingOutputWorker, FeedingRTPParams, WaveChunker, codec_from_name
from sippy.Rtp.Core.AudioChunk import AudioChunk
from sippy.Rtp.Handlers import RTPHandlers
from sippy.Rtp.Params import RTPParams
from sippy.Rtp.Conf import RTPConf
from sippy.Rtp.EPoint import RTPEPoint


def main():
    parser = argparse.ArgumentParser(description='Loopback RTP G711 between two RTPEPoint instances')
    parser.add_argument('wav', help='path to WAV file')
    parser.add_argument('--codec', default='g711', help='g711 or g722')
    parser.add_argument('--host', default='127.0.0.1', help='local host/address to bind')
    parser.add_argument('--ptime', type=int, default=20, help='RTP ptime in ms')
    parser.add_argument('--chunk-ms', type=int, default=None, help='chunk size in ms (default=ptime * 10)')
    parser.add_argument('--timeout', type=float, default=5.0, help='wait for receiver (seconds)')
    args = parser.parse_args()

    rc = RTPConf()

    handlers_tx = RTPHandlers()
    handlers_tx.writer_cls = FeedingOutputWorker

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

    params_tx = FeedingRTPParams((args.host, 0), on_drain=on_drain, out_ptime=args.ptime)
    params_tx.codec = codec_from_name(args.codec)
    params_rx = RTPParams((args.host, 0), out_ptime=args.ptime)
    params_rx.codec = codec_from_name(args.codec)

    recv_lock = threading.Lock()
    recv_frames = {'count': 0}

    def audio_in(chunk: AudioChunk):
        with recv_lock:
            recv_frames['count'] += chunk.nframes

    ep_tx = RTPEPoint(rc, params_tx, lambda _c: None, handlers=handlers_tx)
    ep_rx = RTPEPoint(rc, params_rx, audio_in)

    tx_addr = ep_tx.rserv.local_addr
    rx_addr = ep_rx.rserv.local_addr

    params_tx_new = FeedingRTPParams((rx_addr[0], rx_addr[1]), on_drain=on_drain,
                                     out_ptime=args.ptime)
    params_tx_new.codec = codec_from_name(args.codec)
    ep_tx.update(params_tx_new)
    params_rx_new = RTPParams((tx_addr[0], tx_addr[1]), out_ptime=args.ptime)
    params_rx_new.codec = codec_from_name(args.codec)
    ep_rx.update(params_rx_new)

    try:
        done.wait()
    except KeyboardInterrupt:
        ep_tx.writer.end()
    finally:
        chunker.close()

    start = time.monotonic()
    while time.monotonic() - start < args.timeout:
        tx_prcsd = ep_tx.writer.get_frm_ctrs()[1]
        with recv_lock:
            rx_count = recv_frames['count']
        if done.is_set() and rx_count >= tx_prcsd:
            break
        time.sleep(0.05)

    with recv_lock:
        rx_count = recv_frames['count']
    tx_rcvd, tx_prcsd = ep_tx.writer.get_frm_ctrs()

    print(f'TX frames: rcvd={tx_rcvd} prcsd={tx_prcsd}')
    print(f'RX frames: {rx_count}')

    ep_tx.shutdown()
    ep_rx.shutdown()


if __name__ == '__main__':
    main()
