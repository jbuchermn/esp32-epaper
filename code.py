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
from adafruit_ssd1680 import SSD1680

from network import ntp
from fronius_api import FroniusAPI

# Configuration
INVERTER_IP = "192.168.99.240"

# Display pins for Waveshare 2.13inch e-ink (SD1680)
SPI_CLK = board.IO13
SPI_MOSI = board.IO14
CS = board.IO15
DC = board.IO27
RST = board.IO26
BUSY = board.IO25

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

        # Font for text
        self.font = terminalio.FONT

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

    def update(self, fronius_api):
        """Display power data on e-ink screen"""

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
        line_height_1 = 14
        line_height_2 = 24

        data = fronius_api.get_current_data()
        data['P_Load'] = (data['P_Grid'] + data['P_Akku'] + data['P_PV'])

        if data is None:
            self._add_text("Failed to get data...", x_position, y_position, scale=2)
            y_position += line_height_2
        else:
            for v, k in [('PV:', 'P_PV'), ('Netz:', 'P_Grid'), ('Last:', 'P_Load')]:
                self._add_text(f"{v:<5} {(data[k]/1000.0):6.3f} kW", x_position, y_position, scale=2)
                y_position += line_height_2

            for v, k in [('Akku:', 'SOC'), ('Autarkie:', 'Autonomy')]:
                self._add_text(f"{v:<10} {data[k]:3.0f} %", x_position, y_position, scale=1)
                y_position += line_height_1

        now = ntp.datetime
        now_str = "{:02d}:{:02d}:{:02d}".format(now.tm_hour, now.tm_min, now.tm_sec)
        self._add_text(now_str, x_position, y_position)
        y_position += line_height_1

        # Refresh
        self.display.refresh()

    def _add_text(self, text, x, y, scale=1):
        """Add text label to display"""
        text_area = label.Label(self.font, text=text, scale=scale, color=0x0)
        text_area.x = x
        text_area.y = y
        text_area.anchored_position = (x, y)
        self.splash.append(text_area)


class EnergyMonitor:
    def __init__(self):
        self.api = FroniusAPI(INVERTER_IP)
        self.display = EPaperDisplay()

        self.last_gc = time.time()

    def run(self):
        """Main application loop"""
        print("Starting Energy Monitor...")

        # Test connection to inverter
        if not self.api.test_connection():
            print("Warning: Could not connect to inverter. Check IP address and network.")

        print("Energy Monitor running...")

        while True:
            try:
                current_time = time.time()
                print(f"Memory: {gc.mem_free()}b")

                # Update display
                self.display.update(self.api)

                # Periodic garbage collection
                if current_time - self.last_gc >= 300:  # Every 5 minutes
                    self.last_gc = current_time
                    print("Collecting garbage...")
                    gc.collect()

            except KeyboardInterrupt:
                print("Shutting down...")
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(5)  # Wait before retrying

if __name__ == "__main__":
    monitor = EnergyMonitor()
    monitor.run()
