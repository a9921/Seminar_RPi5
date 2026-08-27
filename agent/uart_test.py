import time
import serial
import json

SERIAL_PORT = "/dev/ttyAMA0"
BAUD = 115200

ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)

ser.reset_input_buffer()

def read_pico():
	raw = ser.readline()

	if not raw:
		return None

	text = raw.decode().strip()

	try:
		return json.loads(text)
	except json.JSONDecodeError:
		return None

while True:
	data = read_pico()

	if data is None
		print("...沒收到完整資料")
	else
		print(f"距離 {data['dist_mm']} mm, 狀態 {data['state']}, 門 {data['door']}")