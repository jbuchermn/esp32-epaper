## Goal

The goal is to build a micropython application which reads data from a Fronius inverter and displays it on an e-ink screen.

## Environment

- Fronius inverter
- Waveshare 2.13inch e-ink display (SD1680, 250x122)
- ESP32
- CircuitPython
    - SSD1680 library installed on ESP32: https://github.com/adafruit/Adafruit_CircuitPython_SSD1680
- Connections:
    - SPI: CLK=board.IO13, MOSI=board.IO14
    - CS=board.IO15
    - DC=board.IO27
    - RST=board.IO26
    - BUSY=board.IO25

## Details

- Every 15s: Get the current data for power (grid, battery, PV) and store it in an array (at most 24h)
- Every 3min:
    - Display avg powers of the last 3min
        - PV
        - Grid - negative values (power sent to grid)
        - Grid - positive values (power from grid)
        - Battery
        - Load (Consumption)
    - Display degree of self-sufficiency over the last 24h (or as long as we have data): Self-sufficiency is defined as
        (energy consumed - energy from grid) / energy_consumed
    - Display a simple chart of the load over the last 24h (or as long as we have data)
