# plintools for LIN bus on PEAK PCAN-LIN/PCAN-USB Pro FD

## Installation
```
$ pip install git+https://github.com/trnila/plintools
```

## TUI LIN signal viewer
```
$ plintools monitor my.ldf /dev/plin0
```

## Dump signals
```
$ plintools dump my.ldf /dev/plin0 --frame MY_FRAME --frame 0x12
$ plintools dump my.ldf /dev/plin0 --node sensor_1 --node sensor_2
$ plintools dump my.ldf /dev/plin0 --master
$ plintools dump my.ldf /dev/plin0 --no-signals
```

## Signal generator
Generates random signals according to LDF file.
```
$ plintools gen my.ldf /dev/plin0
```

## Plotjuggler UDP streamer
Streams decoded signals into [PlotJuggler](https://github.com/facontidavide/PlotJuggler) for graph plotting.

```
$ plintools plotjuggler my.ldf /dev/plin0
```
