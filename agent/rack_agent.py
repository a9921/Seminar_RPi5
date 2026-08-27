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

CMD_TOPIC = "rack/security/cmd"

def read_door():
    with open(DEVICE_PATH) as f:
        data = json.loads(f.read())
    return data["door_state_num"]

def read_pico():
    raw = ser.readline()

    if not raw:
        return None

    text = raw.decode().strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
    
def on_cmd(client, userdata, msg):
    global armed, alarm

    payload = json.loads(msg.payload.decode())
    action = payload["action"]

    if action == "ARM":
        armed = True
    elif action == "DISARM":
        armed = False
    elif action == "RESET_ALARM":
        alarm = False

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rack-security")

client.will_set(TOPIC, json.dumps({"online": False}), 1, True)
client.connect(BROKER, PORT, 60)
client.on_message = on_cmd
client.subscribe(CMD_TOPIC, 1)
client.loop_start()
client.publish(TOPIC, json.dumps({"online": True}), 1, True)

ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
ser.reset_input_buffer()

last_pico = None

armed = True
alarm = False
prev_door = read_door()


while True:
    door = read_door()
    data = read_pico()

    if door == 1 and prev_door == 0 and armed:
        alarm = True
    prev_door = door
    print(f"armed {armed}, alarm {alarm}")

    if door == 1:
        print("door_state = open")
    else:
        print("door_state = close")

    if data is None:
        print("...沒收到完整資料")
    else:
        last_pico = data
        print(f"距離 {data['dist_mm']} mm, 狀態 {data['state']}, 門 {data['door']}, armed {door[armed]}, alarm {door[alarm]}")
