# plintools for LIN bus on PEAK PCAN-LIN/PCAN-USB Pro FD

## Installation
```
$ pip install git+https://github.com/trnila/plintools
```

## TUI LIN signal viewer
```
$ plintools monitor my.ldf /dev/plin0
```

## Signal generator
Generates random signals according to LDF file.
```
$ plintools gen my.ldf /dev/plin0
```
