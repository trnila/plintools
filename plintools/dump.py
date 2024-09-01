from plin.device import PLIN, PLINMessage
from plin.enums import PLINMode, PLINFrameErrorFlag
import ldfparser
import argparse
import os
from rich import print
from rich.table import Table
from rich.markup import escape
from rich.console import Console

stderr = Console(stderr=True, style="red")


class DumpCommand:
    def parser(self, parser: argparse.ArgumentParser):
        parser.add_argument("ldf_path")
        parser.add_argument("device")
        parser.add_argument(
            "--frame",
            "-f",
            action="append",
            help="Show only this frame identified by its ID or name",
        )
        parser.add_argument(
            "--master", "-m", action="store_true", help="Show master frames only"
        )
        parser.add_argument(
            "--node", "-n", action="append", help="Show frames from this node"
        )

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

    def get_allowed_frames(self, ldf: ldfparser.LDF, frames, master, nodes):
        nodes = set(nodes or [])
        all_nodes = set([node.name for node in ldf.slaves] + [ldf.master.name])
        if nodes - all_nodes:
            stderr.print("Unknown nodes:", ", ".join(nodes - all_nodes))
            stderr.print("Available nodes are: ")
            stderr.print("\n".join(sorted(all_nodes - nodes)))
            exit(1)
        if master:
            nodes.add(ldf.master.name)

        requested_frame_ids = []
        if frames:
            for frame in frames:
                if frame.startswith("0x"):
                    frame = int(frame, 16)
                try:
                    requested_frame_ids.append(ldf.get_frame(frame).frame_id)
                except LookupError:
                    stderr.print(f"Frame {frame} not found.")
                    stderr.print("Available frames:")
                    stderr.print("\n".join([frame.name for frame in ldf.frames]))
                    exit(1)

        def is_frame_allowed(frame: ldfparser.LinFrame):
            if requested_frame_ids and frame.frame_id not in requested_frame_ids:
                return False

            if isinstance(frame, ldfparser.LinUnconditionalFrame) and nodes:
                if frame.publisher.name not in nodes:
                    return False

            return True

        return set([f.frame_id for f in ldf.frames if is_frame_allowed(f)])

    def run(self, args):
        ldf = ldfparser.parse_ldf(path=args.ldf_path)
        pub_width = max(len(ldf.master.name), max([len(p.name) for p in ldf.slaves]))
        signal_width = self.get_longest_signal(ldf)
        logical_width = self.get_longest_logical(ldf)

        plin = PLIN(interface=args.device)
        plin.start(mode=PLINMode.SLAVE, baudrate=ldf.get_baudrate())
        plin.set_id_filter(bytearray([0xFF] * 8))

        allowed_frames = self.get_allowed_frames(
            ldf, args.frame, args.master, args.node
        )
        if not allowed_frames:
            stderr.print("Filter removes all frames!")
            exit(1)
        print("Filtered frames:", ", ".join([f"0x{f:02x}" for f in allowed_frames]))

        ts_offset_us = None
        while True:
            try:
                received = os.read(plin.fd, PLINMessage.buffer_length)
                received = PLINMessage.from_buffer_copy(received)
                if received.id not in allowed_frames:
                    continue

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
