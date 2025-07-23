import network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
nets = wlan.scan()
for net in nets:
    print(net[0].decode())  # แสดงชื่อ SSID