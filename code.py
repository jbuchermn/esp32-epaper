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

from fronius_api import FroniusAPI
from data_manager import DataManager

# Configuration
INVERTER_IP = "192.168.99.240"
DATA_COLLECTION_INTERVAL = 15

# Display pins for Waveshare 2.13inch e-ink (SD1680)
SPI_CLK = board.IO13
SPI_MOSI = board.IO14
CS = board.IO15
DC = board.IO27
RST = board.IO26
BUSY = board.IO25

class EPaperDisplay:
    def __init__(self, ntp):
        self._ntp = ntp

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

    def update(self, data_manager):
        """Display power data on e-ink screen"""

        if  self.display.time_to_refresh > 0.5:
            return
        else:
            time.sleep(self.display.time_to_refresh + 0.01)
        print("Updating display...")

        # Get 3-minute averages
        averages = data_manager.get_averages(180)  # 3 minutes

        # Calculate self-sufficiency for last 24 hours
        self_sufficiency = data_manager.calculate_self_sufficiency(24 * 60 * 60)

        # Get load history for chart
        load_history = data_manager.get_load_history(24 * 60 * 60)

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
        y_position = 5
        line_height = 14

        # Power values
        self._add_text(f"PV:          {(averages['pv_power']/1000.0):6.3f} kW", 5, y_position)
        y_position += line_height

        self._add_text(f"Last:        {(averages['load_power']/1000.0):6.3f} kW", 5, y_position)
        y_position += line_height

        self._add_text(f"Netz:        {(averages['grid_import']/1000.0):6.3f} kW", 5, y_position)
        y_position += line_height

        self._add_text(f"Einspeisung: {(averages['grid_export']/1000.0):6.3f} kW", 5, y_position)
        y_position += line_height

        self._add_text(f"Akku:        {(averages['battery_power']/1000.0):6.3f} kW", 5, y_position)
        y_position += line_height

        self._add_text(f"Autarkie:     {self_sufficiency:.1f} %", 5, y_position)
        y_position += line_height

        now = self._ntp.datetime
        now_str = "{:02d}:{:02d}:{:02d}".format(now.tm_hour, now.tm_min, now.tm_sec)
        self._add_text(now_str, 5, y_position)
        y_position += line_height


        # Simple chart on the right side
        if load_history:
            self._draw_simple_chart(load_history, 150, 5, 250-150-5, 122-5)

        self.display.refresh()

    def _add_text(self, text, x, y, color=0x000000):
        """Add text label to display"""
        text_area = label.Label(self.font, text=text, color=color)
        text_area.x = x
        text_area.y = y
        text_area.anchored_position = (x, y)
        self.splash.append(text_area)

    def _draw_simple_chart(self, data, x, y, width, height):
        """Draw a bar chart with one column per data point"""
        if not data:
            return

        # Create a bitmap for the chart
        chart_bitmap = displayio.Bitmap(width, height, 2)
        chart_palette = displayio.Palette(2)
        chart_palette[0] = 0xFFFFFF  # White background
        chart_palette[1] = 0x000000  # Black bars

        # Fill background
        for i in range(width * height):
            chart_bitmap[i] = 0

        # Process data: if we have more data points than width, aggregate to cover 24h
        processed_data = self._process_data_for_chart(data, width)

        # Normalize data
        max_val = max(processed_data) if max(processed_data) > 0 else 1
        normalized_heights = [int((val / max_val) * (height - 2)) for val in processed_data]

        # Draw bar chart - one column per data point
        for i, bar_height in enumerate(normalized_heights):
            if i < width:  # Ensure we don't exceed bitmap width
                # Draw bars from bottom up
                for h in range(bar_height):
                    y_pos = height - 1 - h
                    chart_bitmap[y_pos * width + i] = 1

        # Create tile grid for chart
        chart_sprite = displayio.TileGrid(chart_bitmap, pixel_shader=chart_palette, x=x, y=y)
        self.splash.append(chart_sprite)

    def _process_data_for_chart(self, data, max_width):
        """Process data to fit chart width, using maximum values for aggregation"""
        if len(data) <= max_width:
            return data

        # Calculate how many data points to aggregate per column
        points_per_column = len(data) / max_width

        processed_data = []
        for i in range(max_width):
            # Determine the range of data points for this column
            start_idx = int(i * points_per_column)
            end_idx = int((i + 1) * points_per_column)

            # Get the data slice for this column
            column_data = data[start_idx:end_idx]

            # Use maximum value for this column (emphasizes peaks)
            if column_data:
                processed_data.append(max(column_data))
            else:
                processed_data.append(0)

        return processed_data


class EnergyMonitor:
    def __init__(self):
        self.api = FroniusAPI(INVERTER_IP)
        self.display = EPaperDisplay(self.api.ntp)
        self.data_manager = DataManager(max_hours=24)

        self.last_data_collection = time.time() - DATA_COLLECTION_INTERVAL
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
                print(f"Memory: {gc.mem_free()}b")
                # Small delay to prevent tight loop
                time.sleep(1)

                current_time = time.time()

                # Collect data every 15 seconds
                if current_time - self.last_data_collection >= DATA_COLLECTION_INTERVAL:
                    self.last_data_collection = current_time

                    print("Collecting data from inverter...")
                    data = self.api.get_current_data()
                    if data:
                        self.data_manager.add_data_point(data)
                        print(f"Data collected: PV={data['pv_power']:.0f}W, Grid={data['grid_power']:.0f}W, "
                              f"Battery={data['battery_power']:.0f}W, Load={data['load_power']:.0f}W")
                    else:
                        print("Failed to collect data")

                # Update display
                self.display.update(self.data_manager)

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
