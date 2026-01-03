try:
    import requests
except:
    import wifi
    import adafruit_requests
    import adafruit_connection_manager
    from adafruit_ntp import NTP
    from adafruit_datetime import datetime, timedelta, timezone

    _pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
    _ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)

    requests = adafruit_requests.Session(_pool, _ssl_context)

    _ntp = NTP(_pool, cache_seconds=3600)

    # CEST / CET
    def now():
        t = _ntp.datetime
        utc_now = datetime(t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)
        year = utc_now.year
        march_31 = datetime(year, 3, 31)
        dst_start = march_31 - timedelta(days=(march_31.weekday() + 1) % 7)
        october_31 = datetime(year, 10, 31)
        dst_end = october_31 - timedelta(days=(october_31.weekday() + 1) % 7)
        if dst_start <= utc_now < dst_end:
            offset = 2  # Summer
        else:
            offset = 1  # Winter

        return utc_now + timedelta(hours=offset)
