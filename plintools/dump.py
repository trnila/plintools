from plin.device import PLIN, PLINMessage
from plin.enums import PLINMode, PLINFrameErrorFlag
import ldfparser
import argparse
import os
from rich import print
from rich.table import Table
from rich.markup import escape


class DumpCommand:
    def parser(self, parser: argparse.ArgumentParser):
        parser.add_argument("ldf_path")
        parser.add_argument("device")

    def get_longest_signal(self, ldf: ldfparser.LDF) -> int:
        max_found = 0
        for frame in ldf.frames:
            max_found = max(max_found, max([len(s.name) for _, s in frame.signal_map]))
        return max_found

    def get_longest_logical(self, ldf: ldfparser.LDF) -> int:
        max_found = 0
        for encoding in ldf.get_signal_encoding_types():
            for converter in encoding.get_converters():
                if isinstance(converter, ldfparser.LogicalValue):
                    max_found = max(max_found, len(converter.info))
        return max_found

    def run(self, args):
        ldf = ldfparser.parse_ldf(path=args.ldf_path)
        pub_width = max(len(ldf.master.name), max([len(p.name) for p in ldf.slaves]))
        signal_width = self.get_longest_signal(ldf)
        logical_width = self.get_longest_logical(ldf)

        plin = PLIN(interface=args.device)
        plin.start(mode=PLINMode.SLAVE, baudrate=ldf.get_baudrate())
        plin.set_id_filter(bytearray([0xFF] * 8))

        ts_offset_us = None

        while True:
            try:
                received = os.read(plin.fd, PLINMessage.buffer_length)
                received = PLINMessage.from_buffer_copy(received)

                if not ts_offset_us:
                    ts_offset_us = received.ts_us

                frame = ldf.get_frame(received.id)
                signals = frame.decode(received.data)
                signals_raw = frame.decode_raw(received.data)

                print(
                    f"{(received.ts_us - ts_offset_us) // 1000:>8} 0x{frame.frame_id:02x} [blue]{bytes(received.data).hex(' ').upper()}[/] {frame.publisher.name.ljust(pub_width)} [yellow]{frame.name}[/]"
                )
                if received.flags:
                    print(f"[red]{escape(str(PLINFrameErrorFlag(received.flags)))}[/]")
                else:
                    table = Table()
                    table.add_column(style="cyan", width=signal_width)
                    table.add_column(
                        justify="right", style="magenta", width=logical_width
                    )
                    table.add_column(justify="right", style="green", width=10)
                    table.add_column(justify="right", style="green", width=10)
                    table.show_header = False
                    table.border_style = None
                    table.show_edge = False
                    table.row_styles = ["dim", ""]

                    for name, value in signals.items():
                        table.add_row(
                            name,
                            str(value),
                            str(signals_raw[name]),
                            str(hex(signals_raw[name])),
                        )
                    print(table)
            except Exception as e:
                print(f"[red]Error: {escape(str(e))}[/]")
            except KeyboardInterrupt:
                break
