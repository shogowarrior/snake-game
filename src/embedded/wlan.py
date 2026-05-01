# Wlan / webrepl disabled — networking is intentionally off for now.
# Re-enable by un-commenting below and creating a `secrets.py` on the device
# with `SSID` and `PASSWORD`.

# import secrets  # type: ignore
# from time import sleep
#
# import network  # type: ignore
# import webrepl  # type: ignore
#
# SLEEP_TIME_SECS = 2
#
#
# def wlan_connect():
#     wlan = network.WLAN(network.STA_IF)
#     wlan.ifconfig(("192.168.0.202", "128.128.128.0", "192.168.0.1", "192.168.0.1"))
#     wlan.active(True)
#     wlan.config(dhcp_hostname="snake.local")
#     if not wlan.isconnected():
#         print("connecting to network...")
#         wlan.connect(secrets.SSID, secrets.PASSWORD)
#         sleep(SLEEP_TIME_SECS)
#     print("network config:", wlan.ifconfig())
#
#
# def start_wlan():
#     wlan_connect()
#     webrepl.start()
