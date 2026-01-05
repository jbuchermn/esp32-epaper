from network import requests

class InfluxAPI:
    def __init__(self, url, org, token):
        self._url = url
        self._org = org
        self._token = token

    def get_point(self, query):
        headers = {
            'Authorization': f'Token {self._token}',
            'Content-Type': 'application/vnd.flux'
        }
        with requests.post(
            f'{self._url}/api/v2/query?org={self._org}',
            headers=headers,
            data=query
            ) as response:

            # print(response.text)

            if response.status_code not in [200, 201, 202]:
                print(response.text)
                return None

            data = response.text
            lines = data.strip().split('\n')

            col=None
            for line in lines:
                parts = [l.strip() for l in line.split(',')]
                if col is None and '_value' in parts:
                    col = parts.index('_value')
                elif col is not None and len(parts) > col:
                    try:
                        return float(parts[col])
                    except (ValueError, IndexError):
                        continue
            return None

if __name__ == '__main__':
    import os

    INFLUX_URL=os.getenv("INFLUX_URL")
    INFLUX_ORG=os.getenv("INFLUX_ORG")
    INFLUX_TOKEN=os.getenv("INFLUX_TOKEN")

    print(
        InfluxAPI(INFLUX_URL, INFLUX_ORG, INFLUX_TOKEN).get_point("""
from(bucket: "home")
  |> range(start: -1d)
  |> filter(fn: (r) => r["_measurement"] == "powerflow-calculated")
  |> keep(columns: ["_time", "_field", "_value"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({r with _value: r.E_PV, _field: "Value"}))
  |> group(columns: ["_field"])
  |> difference()
  |> sum()
            """)
    )
