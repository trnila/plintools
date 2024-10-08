#!/usr/bin/env python3
import argparse
from plintools.monitor import MonitorCommand
from plintools.gen import GenCommand
from plintools.plotjuggler_streamer import PlotjugglerCommand
from plintools.dump import DumpCommand


def main():
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers(dest="command", required=True)

    def class_to_command(c):
        return c.__class__.__name__.replace("Command", "").lower()

    commands = {
        class_to_command(c): c
        for c in [
            MonitorCommand(),
            DumpCommand(),
            GenCommand(),
            PlotjugglerCommand(),
        ]
    }

    for name, mod in commands.items():
        mod.parser(subparser.add_parser(name))

    args = parser.parse_args()
    commands[args.command].run(args)


if __name__ == "__main__":
    main()
