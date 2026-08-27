import json
import time
import serial
import paho.mqtt.client as mqtt

DEVICE_PATH = "/dev/rack_door1"
BROKER = "192.168.69.190"
PORT = 1883
TOPIC = "rack/security/report-in" 

SERIAL_PORT = "/dev/ttyAMA0"
BAUD = 115200

def read_door():
    with open(DEVICE_PATH) as f:
        data = json.loads(f.read())
    return data["door_state_num"]

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rack-security")

client.will_set(TOPIC, json.dumps({"online": False}), 1, True)
client.connect(BROKER, PORT, 60)
client.loop_start()
client.publish(TOPIC, json.dumps({"online": True}), 1, True)

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

last_pico = None

while True:
    door = read_door()
    data = read_pico()

    if door == 1:
        print("door_state = open")
    else:
        print("door_state = close")

    if data is None:
        print("...沒收到完整資料")
    else:
        last_pico = data
        print(f"距離 {data['dist_mm']} mm, 狀態 {data['state']}, 門 {data['door']}")
