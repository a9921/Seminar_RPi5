import json
import time
import paho.mqtt.client as mqtt

DEVICE_PATH = "/dev/rack_door1"
BROKER = "192.168.69.190"
PORT = 1883
TOPIC = "rack/security/report-in" 

def read_door():
    with open(DEVICE_PATH) as f:
        data = json.loads(f.read())
    return data["door_state_num"]

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rack-security")

client.will_set(TOPIC, json.dumps({"online": False}), 1, True)
client.connect(BROKER, PORT, 60)
client.loop_start()
client.publish(TOPIC, json.dumps({"online": True}), 1, True)

while True:
    state = read_door()
    if state == 1:
        print("door_state = open")
    else:
        print("door_state = close")
    time.sleep(1)

