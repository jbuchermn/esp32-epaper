import adafruit_requests
import adafruit_connection_manager
from adafruit_ntp import NTP
import json
import wifi

import time

class FroniusAPI:
    def __init__(self, inverter_ip):
        self.inverter_ip = inverter_ip
        self.base_url = f"http://{inverter_ip}/solar_api/v1"

        self._pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
        self._ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
        self._requests = adafruit_requests.Session(self._pool, self._ssl_context)

        # TODO: Clean up
        self.ntp = NTP(self._pool, cache_seconds=3600)

    def get_current_data(self):
        """Get current power data from Fronius inverter"""
        try:
            # Get common inverter data
            url = f"{self.base_url}/GetPowerFlowRealtimeData.fcgi"
            response = self._requests.get(url, timeout=10)

            if response.status_code == 200:
                data = json.loads(response.text)
                response.close()

                return self._parse_power_flow_data(data)
            else:
                print(f"HTTP Error: {response.status_code}")
                response.close()
                return None

        except Exception as e:
            print(f"Error fetching data from inverter: {e}")
            return None

    def _parse_power_flow_data(self, data):
        """Parse power flow data from Fronius API response"""
        try:
            # Extract data from the response structure
            power_flow = data.get('Body', {}).get('Data', {}).get('Site', {})

            # PV power (always positive when producing)
            pv_power = abs(power_flow.get('P_PV', 0))

            # Grid power (positive when consuming, negative when feeding)
            grid_power = power_flow.get('P_Grid', 0)

            # Battery power (positive when discharging, negative when charging)
            battery_power = power_flow.get('P_Akku', 0)

            # Calculate load power from energy balance: Load = PV + GridImport - BatteryCharging + GridExport + BatteryDischarge
            # Simplified: Load = PV + Grid - Battery (with proper sign handling)
            grid_import = max(0, grid_power)
            grid_export = abs(min(0, grid_power))
            battery_charge = abs(min(0, battery_power))
            battery_discharge = max(0, battery_power)

            # Load = consumption = PV + GridImport + BatteryDischarge - GridExport - BatteryCharge
            load_power = pv_power + grid_import + battery_discharge - grid_export - battery_charge
            load_power = max(0, load_power)  # Ensure load is not negative

            return {
                'pv_power': pv_power,
                'grid_power': grid_power,
                'battery_power': battery_power,
                'load_power': load_power,
                'timestamp': time.time()
            }

        except Exception as e:
            print(f"Error parsing power flow data: {e}")
            return None

    def get_inverter_info(self):
        """Get basic inverter information"""
        try:
            url = f"{self.base_url}/GetInverterInfo.cgi"
            response = self._requests.get(url)

            if response.status_code == 200:
                data = json.loads(response.text)
                response.close()
                return data
            else:
                response.close()
                return None

        except Exception as e:
            print(f"Error getting inverter info: {e}")
            return None

    def test_connection(self):
        """Test connection to the inverter"""
        try:
            info = self.get_inverter_info()
            if info:
                print("Successfully connected to Fronius inverter")
                return True
            else:
                print("Failed to connect to inverter")
                return False
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
