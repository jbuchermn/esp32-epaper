import json
import time

from network import requests

class FroniusAPI:
    def __init__(self, inverter_ip):
        self.inverter_ip = inverter_ip
        self.base_url = f"http://{inverter_ip}/solar_api/v1"

    def get_current_data(self):
        """Get current power data from Fronius inverter"""
        try:
            # Get common inverter data
            url = f"{self.base_url}/GetPowerFlowRealtimeData.fcgi"
            response = requests.get(url, timeout=10)

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
            # print(json.dumps(data, indent=2))
            power_flow = data.get('Body', {}).get('Data', {}).get('Site', {})
            inverter = data.get('Body', {}).get('Data', {}).get('Inverters', {}).get('1', {})

            return {
                'P_PV': power_flow.get('P_PV', 0),
                'P_Akku': power_flow.get('P_Akku', 0),
                'P_Grid': power_flow.get('P_Grid', 0),
                'SOC': inverter.get('SOC', 0),
                'Autonomy': power_flow.get('rel_Autonomy', 0),
                'timestamp': data.get('Head', {}).get('Timestamp', '')
            }

        except Exception as e:
            print(f"Error parsing power flow data: {e}")
            return None

    def get_inverter_info(self):
        """Get basic inverter information"""
        try:
            url = f"{self.base_url}/GetInverterInfo.cgi"
            response = requests.get(url)

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


if __name__ == '__main__':
    api = FroniusAPI('192.168.99.240')
    print(api.get_inverter_info())
    print(api.get_current_data())
