#!/usr/bin/env python3
from plin.device import PLIN
from plin.enums import PLINMode
import ldfparser
import time
import argparse
import random
import sys
from plin.enums import (
    PLINFrameChecksumType,
    PLINFrameDirection,
)


class GenCommand:
    def parser(self, parser: argparse.ArgumentParser):
        parser.add_argument("ldf_path")
        parser.add_argument("device")
        parser.add_argument("--schedule-table", "-s")

    def run(self, args):
        ldf = ldfparser.parse_ldf(path=args.ldf_path)

        plin = PLIN(interface=args.device)
        plin.start(mode=PLINMode.MASTER, baudrate=ldf.get_baudrate())
        plin.set_id_filter(bytearray([0xFF] * 8))

        Generator(ldf, plin).run()


class Generator:
    def __init__(self, ldf: ldfparser.LDF, plin: PLIN):
        self.ldf = ldf
        self.plin = plin

    def fuzz(self, frame_id: int):
        frame = self.ldf.get_frame(frame_id)
        if isinstance(frame, ldfparser.LinUnconditionalFrame):
            signals = {}
            for _, signal in frame.signal_map:
                if isinstance(signal.publisher, ldfparser.node.LinMaster):
                    value = None
                    for conv in signal.encoding_type.get_converters():
                        if isinstance(conv, ldfparser.encoding.PhysicalValue):
                            value = random.randint(conv.phy_min, conv.phy_max)

                    if value is None:
                        value = random.choice(
                            [
                                conf.info
                                for conf in signal.encoding_type.get_converters()
                                if isinstance(conv, ldfparser.encoding.LogicalValue)
                            ]
                        )

                    if value is None:
                        value = random.randint(0, 2**signal.width - 1)

                    signals[signal.name] = value
                    # signals[signal.name] = signal.init_value
                    # print("got", signals[signal.name])

            return frame.encode(signals)

    def create_schedule_tables(self):
        master_frames = []
        for schedule_id, table in enumerate(self.ldf.get_schedule_tables()):
            print(table.name)
            for item in table.schedule:
                if isinstance(item, ldfparser.schedule.LinFrameEntry):
                    frame = self.ldf.get_frame(item.frame.frame_id)
                    if isinstance(frame, ldfparser.frame.LinUnconditionalFrame):
                        direction = (
                            PLINFrameDirection.PUBLISHER
                            if isinstance(frame.publisher, ldfparser.node.LinMaster)
                            else PLINFrameDirection.SUBSCRIBER_AUTO_LEN
                        )

                        data = self.fuzz(frame.frame_id)
                        self.plin.set_frame_entry(
                            frame.frame_id,
                            direction,
                            PLINFrameChecksumType.ENHANCED,
                            data=data,
                            len=len(data),
                        )
                        self.plin.add_unconditional_schedule_slot(
                            schedule_id, int(item.delay * 1000), frame.frame_id
                        )

                        if direction == PLINFrameDirection.PUBLISHER:
                            master_frames.append(frame.frame_id)

                        sender = (
                            "M" if direction == PLINFrameDirection.PUBLISHER else "S"
                        )
                        print(f"  {frame.frame_id:02X} {sender} {frame.name}")
        return list(set(master_frames))

    def run(self, schedule_table=0):
        master_frames = self.create_schedule_tables()

        schedule_id = 0
        if schedule_table:
            found = [
                i
                for i, table in enumerate(self.ldf.get_schedule_tables())
                if table.name.lower() == schedule_table.lower()
            ]
            if not found:
                print(f'Schedule table "{schedule_table}" not found.', file=sys.stderr)
                exit(1)
            schedule_id = found[0]

        self.plin.start_schedule(schedule_id)

        while True:
            frame_id = random.choice(master_frames)

            data = self.fuzz(frame_id)
            self.plin.set_frame_entry_data(frame_id, 0, data, len(data))

            time.sleep(0.1)
