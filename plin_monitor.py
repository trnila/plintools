#!/usr/bin/env python3
from asyncio import events
import contextvars
import functools
from textual.keys import Keys
from textual.app import App, ComposeResult, Binding
from textual.widgets import Footer, DataTable, Label, Static
from plin.device import PLIN, PLINMessage
from plin.enums import PLINMode, PLINFrameErrorFlag
import ldfparser
import time
import argparse
import asyncio
import os


async def to_thread(func, /, *args, **kwargs):
    loop = events.get_running_loop()
    ctx = contextvars.copy_context()
    func_call = functools.partial(ctx.run, func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)


class FrameWidget(Static):
    def __init__(self, frame: ldfparser.LinFrame):
        super().__init__()
        self.frame = frame

    def on_click(self):
        table = self.query_one("DataTable")
        table.display = not table.display

    def compose(self) -> ComposeResult:
        table = DataTable()
        table.show_header = False
        table.add_column("Signal")
        table.add_column("Logical", width=50)
        table.add_column("Physical dec")
        table.add_column("Physical hex")
        table.add_rows([[signal.name] for _, signal in self.frame.signal_map])
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.display = False

        label = Label(f"0x{self.frame.frame_id:02x} {self.frame.name}")
        label.can_focus = True

        yield label
        yield table


class PlinMonitor(App[None]):
    CSS_PATH = "plin_monitor.tcss"
    BINDINGS = (
        Binding(Keys.ControlSpace, "toggle_all_signals()", "toggle all signals"),
        Binding("space", "toggle_signal", "toggle signals"),
        Binding(Keys.Escape, "quit", "quit"),
        Binding("q", "quit", "quit"),
    )

    def __init__(self, ldf: ldfparser.LDF, plin: PLIN):
        super().__init__()
        self.toggle_all_signals = False
        self.plin = plin
        self.ldf = ldf
        self.tables = {}
        self.cache = {}

    def action_toggle_signal(self):
        table = self.focused.parent.query_one("DataTable")
        table.display = not table.display

    def action_toggle_all_signals(self):
        for table in self.tables.values():
            table.query_one("DataTable").display = self.toggle_all_signals
        self.toggle_all_signals = not self.toggle_all_signals

    def compose(self) -> ComposeResult:
        yield Footer()

        for frame in ldf.frames:
            widget = FrameWidget(frame)
            self.tables[frame.frame_id] = widget
            yield widget

        self.bg_task = asyncio.create_task(to_thread(self.pump_frames))

    def pump_frames(self):
        try:
            while True:
                frame = os.read(plin.fd, PLINMessage.buffer_length)
                frame = PLINMessage.from_buffer_copy(frame)
                frame.ts_us = int(time.time_ns() / 1000)
                self.call_from_thread(self.update_frame, frame)
        except Exception as e:
            self._handle_exception(e)

    def update_frame(self, received_frame: PLINMessage):
        try:
            frame = self.ldf.get_frame(received_frame.id)
        except LookupError:
            return
        widget = self.tables[received_frame.id]

        data = bytes(received_frame.data)
        decoded = frame.decode(data)
        decoded_raw = frame.decode_raw(data)

        payload = f'[blue]{data.hex(" ").upper()}[/]'

        if received_frame.flags:
            payload = f"[red]{str(PLINFrameErrorFlag(received_frame.flags))}[/]"

        widget.query_one("Label").update(
            f"0x{received_frame.id:02x} {frame.name} {payload}"
        )

        table = widget.query_one("DataTable")
        if table.display:
            for row, (k, v) in enumerate(decoded.items()):
                key = f"{received_frame.id}-{row}"
                if self.cache.get(key, None) != decoded_raw:
                    table.update_cell_at((row, 1), v)
                    table.update_cell_at((row, 2), decoded_raw[k])
                    table.update_cell_at((row, 3), hex(decoded_raw[k]))
                    self.cache[key] = decoded_raw


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("ldf_path")
    p.add_argument("device")
    args = p.parse_args()

    ldf = ldfparser.parse_ldf(path=args.ldf_path)

    plin = PLIN(interface=args.device)
    plin.start(mode=PLINMode.SLAVE, baudrate=ldf.get_baudrate())
    plin.set_id_filter(bytearray([0xFF] * 8))

    app = PlinMonitor(ldf, plin)
    app.run()
