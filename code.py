import os
import board
import displayio
import busio
import fourwire
import digitalio
import time
import gc
import terminalio
import time

from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font
from adafruit_ssd1680 import SSD1680

from network import now
from fronius_api import FroniusAPI
from influx_api import InfluxAPI

# Display pins for Waveshare 2.13inch e-ink (SD1680)
SPI_CLK = board.IO13
SPI_MOSI = board.IO14
CS = board.IO15
DC = board.IO27
RST = board.IO26
BUSY = board.IO25

# Fonts
TER_U12N = bitmap_font.load_font("ter-u12n.bdf")
TER_U18N = bitmap_font.load_font("ter-u18n.bdf")

class EPaperDisplay:
    def __init__(self):
        # Release any existing displays
        displayio.release_displays()

        # Initialize SPI
        self._spi = busio.SPI(clock=SPI_CLK, MOSI=SPI_MOSI)

        # Initialize display (250x122 resolution)
        self._display_bus = fourwire.FourWire(
            self._spi,
            command=DC,
            chip_select=CS,
            reset=RST,
            baudrate=1000000
        )
        time.sleep(1)

        print("Initialising display...")
        self.display = SSD1680(
            self._display_bus,
            width=250,
            height=122,
            busy_pin=BUSY,
            highlight_color=0xFF0000,
            rotation=270,
            colstart=0,
        )

        # Create main display group
        self.splash = displayio.Group()
        self.display.root_group = self.splash

        # Initialize with clear display
        # self.clear()

    def clear(self):
        """Clear the display"""
        self.splash = displayio.Group()
        self.display.root_group = self.splash

        # Create white background
        color_bitmap = displayio.Bitmap(250, 122, 1)
        color_palette = displayio.Palette(1)
        color_palette[0] = 0xFFFFFF  # White
        bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette)
        self.splash.append(bg_sprite)

        self.display.refresh()

    def _query_influx(self, influx_api):
        queries = {
                'Batt_MAX': """
from(bucket: "fronius")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "storage")
  |> filter(fn: (r) => r["_field"] == "StateOfCharge_Relative")
  |> aggregateWindow(every: 1d, fn: max, createEmpty: false)
  |> mean()
            """,
                'Batt_NOW': """
from(bucket: "fronius")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "storage")
  |> filter(fn: (r) => r["_field"] == "StateOfCharge_Relative")
  |> last()
            """,
                'GridImp_YEAR': """
from(bucket: "home")
  |> range(start: -1y)
  |> filter(fn: (r) => r["_measurement"] == "powerflow-calculated")
  |> keep(columns: ["_time", "_field", "_value"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with _value: r.E_Grid_pos / 1000.0, _field: "Value"}))
  |> group(columns: ["_field"])
  |> difference()
  |> sum()
            """,
                'GridImp_DAY': """
from(bucket: "home")
  |> range(start: -1d)
  |> filter(fn: (r) => r["_measurement"] == "powerflow-calculated")
  |> keep(columns: ["_time", "_field", "_value"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with _value: r.E_Grid_pos / 1000.0, _field: "Value"}))
  |> group(columns: ["_field"])
  |> difference()
  |> sum()
            """,
                'GridExp_YEAR': """
from(bucket: "home")
  |> range(start: -1y)
  |> filter(fn: (r) => r["_measurement"] == "powerflow-calculated")
  |> keep(columns: ["_time", "_field", "_value"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with _value: r.E_Grid_neg / 1000.0, _field: "Value"}))
  |> group(columns: ["_field"])
  |> difference()
  |> sum()
            """,
                'GridExp_DAY': """
from(bucket: "home")
  |> range(start: -1d)
  |> filter(fn: (r) => r["_measurement"] == "powerflow-calculated")
  |> keep(columns: ["_time", "_field", "_value"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with _value: r.E_Grid_neg / 1000.0, _field: "Value"}))
  |> group(columns: ["_field"])
  |> difference()
  |> sum()
            """,
                'PV_YEAR': """
from(bucket: "home")
  |> range(start: -1y)
  |> filter(fn: (r) => r["_measurement"] == "powerflow-calculated")
  |> keep(columns: ["_time", "_field", "_value"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with _value: r.E_PV / 1000.0, _field: "Value"}))
  |> group(columns: ["_field"])
  |> difference()
  |> sum()
            """,
                'PV_DAY': """
from(bucket: "home")
  |> range(start: -1d)
  |> filter(fn: (r) => r["_measurement"] == "powerflow-calculated")
  |> keep(columns: ["_time", "_field", "_value"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with _value: r.E_PV / 1000.0, _field: "Value"}))
  |> group(columns: ["_field"])
  |> difference()
  |> sum()
            """,
                'Load_YEAR': """
from(bucket: "home")
  |> range(start: -1y)
  |> filter(fn: (r) => r["_measurement"] == "powerflow-calculated")
  |> keep(columns: ["_time", "_field", "_value"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with _value: r.E_Load / 1000.0, _field: "Value"}))
  |> group(columns: ["_field"])
  |> difference()
  |> sum()
            """,
                'PV_15MIN': """
from(bucket: "fronius")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "powerflow")
  |> filter(fn: (r) => r["_field"] == "P_PV")
  |> mean()
            """,
        }

        return {k:influx_api.get_point(v) for k, v in queries.items()}


    def update_from_influx(self, influx_api):
        print(f"Waiting for display update: {self.display.time_to_refresh}s...")
        time.sleep(self.display.time_to_refresh + 0.1)

        print("Querying...")
        # TODO: On the second iteration, this breaks (-2, Name or service not known) after a long wait
        vals = self._query_influx(influx_api)

        print("Updating display...")

        # Clear display group
        self.splash = displayio.Group()
        self.display.root_group = self.splash

        # Create white background
        color_bitmap = displayio.Bitmap(250, 122, 1)
        color_palette = displayio.Palette(1)
        color_palette[0] = 0xFFFFFF  # White
        bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette)
        self.splash.append(bg_sprite)

        # PV values top left
        pv_now = vals.get('PV_15MIN', 0)
        self._add_text(f"PV: {pv_now:.0f} W", 10, 10, font=TER_U12N, anchor_point=(0, 0))

        # Autonomy top right
        autonomy = 100. * (1. + vals.get('GridImp_YEAR', 0) / vals.get('Load_YEAR', 1))
        self._add_text(f"Aut.: {autonomy:.0f}%", 240, 10, font=TER_U12N, anchor_point=(1.0, 0))

        # PV values top
        pv_day = vals.get('PV_DAY', 0)
        pv_year = vals.get('PV_YEAR', 0)
        self._add_text("PV", 125, 3, font=TER_U12N, anchor_point=(0.5, 0))
        self._add_text(f"{pv_day:.0f}", 122, 15, font=TER_U18N, anchor_point=(1, 0))
        self._add_text(f"{pv_year:.0f}", 122, 33, font=TER_U12N, anchor_point=(1, 0))
        self._add_text(f"kWh", 128, 31, font=TER_U18N, anchor_point=(0, 0.5))

        # Grid import on left
        imp_day = vals.get('GridImp_DAY', 0)
        imp_year = vals.get('GridImp_YEAR', 0)
        self._add_text("Import", 10, 48, font=TER_U12N)
        self._add_text(f"{imp_day:.0f}", 40, 60, font=TER_U18N, anchor_point=(1, 0))
        self._add_text(f"{imp_year:.0f}", 40, 78, font=TER_U12N, anchor_point=(1, 0))
        self._add_text(f"kWh", 46, 76, font=TER_U18N, anchor_point=(0, 0.5))

        # Grid export on right
        exp_day = vals.get('GridExp_DAY', 0)
        exp_year = vals.get('GridExp_YEAR', 0)
        self._add_text("Export", 240, 48, font=TER_U12N, anchor_point=(1, 0))
        self._add_text(f"{exp_day:.0f}", 210, 60, font=TER_U18N, anchor_point=(1, 0))
        self._add_text(f"{exp_year:.0f}", 210, 78, font=TER_U12N, anchor_point=(1, 0))
        self._add_text(f"kWh", 216, 76, font=TER_U18N, anchor_point=(0, 0.5))

        # Battery bar at bottom
        batt_now = vals.get('Batt_NOW', 0)
        batt_max = vals.get('Batt_MAX', 0)
        self._draw_battery_bar(125 - 6, 54, batt_now, batt_max, width=12, height=40)

        # Time at bottom center
        try:
            n = now()
            self._add_text(f"{n.day:02}.{n.month:02}.{n.year} {n.hour:02}:{n.minute:02}", 125, 122, font=TER_U12N, anchor_point=(0.5, 1.0))
        except:
            self._add_text(f"Offline", 125, 122, font=TER_U12N, anchor_point=(0.5, 1.0))

        # Refresh
        self.display.refresh()


    def update_from_fronius(self, fronius_api):
        print(f"Waiting for display update: {self.display.time_to_refresh}s...")
        time.sleep(self.display.time_to_refresh + 0.1)
        print("Updating display...")

        # Clear display group
        self.splash = displayio.Group()
        self.display.root_group = self.splash

        # Create white background
        color_bitmap = displayio.Bitmap(250, 122, 1)
        color_palette = displayio.Palette(1)
        color_palette[0] = 0xFFFFFF  # White
        bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette)
        self.splash.append(bg_sprite)

        # Add text labels
        x_position = 10
        y_position = 10
        line_height_1 = 16
        line_height_2 = 20

        data = fronius_api.get_current_data()
        data['P_Load'] = (data['P_Grid'] + data['P_Akku'] + data['P_PV'])

        if data is None:
            self._add_text("Failed to get data...", x_position, y_position, font=TER_U18N)
            y_position += line_height_2
        else:
            for v, k in [('PV:', 'P_PV'), ('Netz:', 'P_Grid'), ('Last:', 'P_Load')]:
                self._add_text(f"{v:<5} {(data[k]/1000.0):6.3f} kW", x_position, y_position, font=TER_U18N)
                y_position += line_height_2

            for v, k in [('Akku:', 'SOC'), ('Autarkie:', 'Autonomy')]:
                self._add_text(f"{v:<10} {data[k]:3.0f} %", x_position, y_position, font=TER_U12N)
                y_position += line_height_1

        n = now()
        self._add_text(str(n), 120, 110, font=TER_U12N)
        y_position += line_height_1

        # Refresh
        self.display.refresh()

    def _add_text(self, text, x, y, font=TER_U12N, anchor_point=(0, 0)):
        """Add text label to display"""
        text_area = label.Label(font, text=text, color=0x0, anchor_point=anchor_point)
        text_area.x = x
        text_area.y = y
        text_area.anchored_position = (x, y)
        self.splash.append(text_area)

    def _draw_battery_bar(self, x, y, current_value, max_value, width=10, height=40):
        """Draw vertical battery bar with black outline and filled current value"""
        # Ensure current value is within bounds
        current_value = max(0, min(100, current_value))

        # Create battery outline (black border)
        outline_bitmap = displayio.Bitmap(width, height, 1)
        outline_palette = displayio.Palette(2)
        outline_palette[0] = 0xFFFFFF  # White (transparent)
        outline_palette[1] = 0x000000  # Black border

        # Draw border pixels (top, bottom, left, right)
        for i in range(width):
            outline_bitmap[i, 0] = 1  # Top border
            outline_bitmap[i, height-1] = 1  # Bottom border
        for i in range(height):
            outline_bitmap[0, i] = 1  # Left border
            outline_bitmap[width-1, i] = 1  # Right border

        outline_sprite = displayio.TileGrid(outline_bitmap, pixel_shader=outline_palette, x=x, y=y)
        self.splash.append(outline_sprite)

        # Draw filled portion for current value
        if current_value > 0:
            fill_height = int((current_value / 100.0) * (height - 2))  # Leave space for borders
            fill_height = max(0, min(fill_height, height - 2))

            if fill_height > 0:
                fill_bitmap = displayio.Bitmap(width - 2, fill_height, 1)
                fill_palette = displayio.Palette(1)
                fill_palette[0] = 0x000000  # Black fill

                # Position fill from bottom up
                fill_y = y + height - 1 - fill_height
                fill_sprite = displayio.TileGrid(fill_bitmap, pixel_shader=fill_palette, x=x + 1, y=fill_y)
                self.splash.append(fill_sprite)


        # Draw max line
        max_bitmap = displayio.Bitmap(width + 2, 1, 1)
        max_palette = displayio.Palette(1)
        max_palette[0] = 0x000000  # Black fill
        max_y = y + height - 1 - int((max_value / 100.0) * (height - 2))
        max_sprite = displayio.TileGrid(max_bitmap, pixel_shader=max_palette, x=x - 1, y=max_y)
        self.splash.append(max_sprite)


class EnergyMonitor:
    def __init__(self):
        self.fronius_api = FroniusAPI(os.getenv("INVERTER_IP"))
        self.influx_api = InfluxAPI(
            os.getenv("INFLUX_URL"),
            os.getenv("INFLUX_ORG"),
            os.getenv("INFLUX_TOKEN")
        )
        self.display = EPaperDisplay()

        self.last_gc = time.time()

    def run(self):
        # Test connection to inverter
        # if not self.fronius_api.test_connection():
        #     print("Warning: Could not connect to inverter. Check IP address and network.")

        print("Main loop...")

        while True:
            try:
                # Prevent tight loop
                time.sleep(1)

                # Periodic garbage collection
                current_time = time.time()
                if current_time - self.last_gc >= 300:  # Every 5 minutes
                    self.last_gc = current_time
                    print("Collecting garbage...")
                    gc.collect()
                    print(f"Memory: {gc.mem_free()}b")

                # print("Collecting garbage...")
                # gc.collect()
                # print(f"Memory: {gc.mem_free()}b")

                # Update display
                self.display.update_from_influx(self.influx_api)
                # self.display.update_from_fronius(self.fronius_api)

            except KeyboardInterrupt:
                print("Shutting down...")
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(5)  # Wait before retrying

if __name__ == "__main__":
    monitor = EnergyMonitor()
    monitor.run()
