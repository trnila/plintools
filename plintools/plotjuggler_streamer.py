#!/usr/bin/env python3
import socket
import json
import time
import argparse
import ldfparser
from plin.device import PLIN
from plin.enums import PLINMode


class PlotjugglerCommand:
    def parser(self, parser: argparse.ArgumentParser):
        parser.add_argument("ldf_path")
        parser.add_argument("device")
        parser.add_argument(
            "--dst", default="127.0.0.1", help="UDP destination for sending samples"
        )
        parser.add_argument("--port", default=9870, help="UDP port for sending samples")

    def run(self, args):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        ldf = ldfparser.parse_ldf(path=args.ldf_path)

        plin = PLIN(interface=args.device)
        plin.start(mode=PLINMode.SLAVE, baudrate=ldf.get_baudrate())
        plin.set_id_filter(bytearray([0xFF] * 8))

        while True:
            try:
                received = plin.read()
                if not received:
                    continue

                frame = ldf.get_frame(received.id)
                decoded = frame.decode_raw(received.data)
                sample = {
                    "ts": time.time(),
                    frame.publisher.name: decoded,
                }

                s.sendto(json.dumps(sample).encode(), (args.dst, args.port))
            except Exception as e:
                print(e)
