#!/usr/bin/env python3
from plin.device import PLIN
from plin.enums import PLINMode
import ldfparser
import curses
import time
import argparse

p = argparse.ArgumentParser()
p.add_argument('ldf_path')
p.add_argument('device')
args = p.parse_args()


class PlinMonitor:
    def __init__(self, stdscr, ldf, plin):
        self.stdscr = stdscr
        self.ldf = ldf
        self.plin = plin
        self.row = 0
    
    def run(self):
        longest_signal = max([len(s.name) for s in self.ldf.signals])

        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)
        curses.use_default_colors()
        curses.curs_set(False)
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)

        messages = {}
        while True:
            while True:
                result = self.plin.read(block=False)
                if not result:
                    break

                result.ts_us = int(time.time_ns() / 1000)
                messages[result.id] = result

            self.stdscr.erase()
            self.row = 0

            for id, result in messages.items():
                data = bytes(result.data)
                frame = self.ldf.get_frame(id)
                decoded = frame.decode(data)
                decoded_raw = frame.decode_raw(data)

                missing = (time.time_ns() / 1000 - result.ts_us) > 1000 * 1000
                self.add_row(f"{id:02x} {frame.publisher.name} {data.hex(' ')}", 4 if missing else 3)
                for k, v in decoded.items():
                    s = [f"{v:>3}"]
                    if v != decoded_raw[k]:
                        s.append(f"{decoded_raw[k]:>3}") 
                    s.append(f"0x{decoded_raw[k]:02x}")

                    self.add_row(f' {k.rjust(longest_signal)}: {" ".join(s)}')

            self.stdscr.refresh()
            time.sleep(0.05)

    def add_row(self, text, color=0):
        self.stdscr.addstr(self.row, 0, str(text), curses.color_pair(color))
        self.row += 1

def app(stdscr):
    ldf = ldfparser.parse_ldf(path=args.ldf_path)
    
    plin = PLIN(interface=args.device)
    plin.start(mode=PLINMode.SLAVE, baudrate=ldf.get_baudrate())
    plin.set_id_filter(bytearray([0xff] * 8))

    PlinMonitor(stdscr, ldf, plin).run()


def main():
    try:
        curses.wrapper(app)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()