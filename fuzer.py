#!/usr/bin/env python3
from plin.device import PLIN
from plin.enums import PLINMode
import ldfparser
import time
import argparse
import random
from plin.enums import (
    PLINFrameChecksumType,
    PLINFrameDirection,
)

p = argparse.ArgumentParser()
p.add_argument("ldf_path")
p.add_argument("device")
args = p.parse_args()


ldf = ldfparser.parse_ldf(path=args.ldf_path)

plin = PLIN(interface=args.device)
plin.start(mode=PLINMode.MASTER, baudrate=ldf.get_baudrate())
plin.set_id_filter(bytearray([0xFF] * 8))


def fuzz(frame_id: int):
    frame = ldf.get_frame(frame_id)
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


master_frames = []
for schedule_id, table in enumerate(ldf.get_schedule_tables()):
    for item in table.schedule:
        if isinstance(item, ldfparser.schedule.LinFrameEntry):
            frame = ldf.get_frame(item.frame.frame_id)
            if isinstance(frame, ldfparser.frame.LinUnconditionalFrame):
                direction = (
                    PLINFrameDirection.PUBLISHER
                    if isinstance(frame.publisher, ldfparser.node.LinMaster)
                    else PLINFrameDirection.SUBSCRIBER_AUTO_LEN
                )
                if direction != PLINFrameDirection.PUBLISHER:
                    continue
                data = fuzz(frame.frame_id)
                plin.set_frame_entry(
                    frame.frame_id,
                    direction,
                    PLINFrameChecksumType.ENHANCED,
                    data=data,
                    len=len(data),
                )
                plin.add_unconditional_schedule_slot(
                    schedule_id, int(item.delay * 1000), frame.frame_id
                )
                print(hex(frame.frame_id), frame.name)

                if direction == PLINFrameDirection.PUBLISHER:
                    master_frames.append(frame.frame_id)
                    print("add ", hex(frame.frame_id))

    plin.start_schedule(schedule_id)
    break

master_frames = list(set(master_frames))

while True:
    frame_id = random.choice(master_frames)

    data = fuzz(frame_id)
    plin.set_frame_entry_data(frame_id, 0, data, len(data))

    time.sleep(0.1)
