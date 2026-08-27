from gpiozero import DigitalInputDevice
import time

DOOR_PIN = 17          # GPIO 編號（實體第 11 腳）

sensor = DigitalInputDevice(DOOR_PIN)

print("霍爾感測器測試開始。拿磁鐵靠近、遠離，觀察數值變化。")
print("按 Ctrl+C 結束。\n")

prev = None
try:
	while True:
		v = sensor.value               # 讀到 0 或 1
		if v != prev:                  # 只在變化時印出，避免洗版
			print(f"訊號 = {v}")
			prev = v
		time.sleep(0.05)
except KeyboardInterrupt:
	print("\n結束。")
