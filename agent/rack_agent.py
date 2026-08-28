import json
import time
import serial
import paho.mqtt.client as mqtt
import os

DEVICE_PATH = "/dev/rack_door1"
BROKER = "192.168.69.190"
PORT = 1883
TOPIC = "rack/security/report-in" 

SERIAL_PORT = "/dev/ttyAMA0"
BAUD = 115200

CMD_TOPIC = "rack/security/cmd"

TELEMETRY_TOPIC = "rack/security/telemetry"
TELEMETRY_INTERVAL = 5

STATE_NAME = {
    0: "error",
    1: "normal",
    2: "warn",
    3: "alert",
    4: "anomaly",
}
STATE_TOPIC = "rack/security/state"
EVENT_TOPIC = "rack/security/event"

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

if not os.path.exists(DEVICE_PATH):
    print(f"x 找不到 {DEVICE_PATH}")
    print("  核心模組未載入。請先執行:")
    print("  sudo insmod ~/Seminar/kmod/rack_door.ko")
    raise SystemError(1)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rack-security")

client.will_set(TOPIC, json.dumps({"online": False}), 1, True)
try:
    client.connect(BROKER, PORT, 60)
    mqtt_ok = True
except OSError as e:
    print(f"▲ MQTT 連線失敗: {e}")
    print(" 以離線模式繼續，門、UART、超音波、燈條功能不受影響")
    mqtt_ok = False

client.on_message = on_cmd

if mqtt_ok:
    client.subscribe(CMD_TOPIC, 1)
    client.loop_start()
    client.publish(TOPIC, json.dumps({"online": True}), 1, True)

ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
ser.reset_input_buffer()

last_pico = None

armed = True
alarm = False
prev_door = read_door()
ser.write(b"D" if prev_door == 1 else b"C")
prev_armed = None
prev_alarm = False

last_telemetry = 0.0

try:
    while True:
        door = read_door()
        data = read_pico()
        now = time.time()

        if now - last_telemetry >= TELEMETRY_INTERVAL:
            last_telemetry = now

            if last_pico is None:
                pico_state = "error"
            else:
                pico_state = STATE_NAME.get(last_pico["state"], "error")

            payload = {
                "timestamp": int(time.time()),
                "pico_state": pico_state,
                "door_rack": "open" if door == 1 else "close",
            }

            client.publish(TELEMETRY_TOPIC, json.dumps(payload), 0, False)
            print("→ telemetry", payload)

        if door == 1 and prev_door == 0 and armed:
            alarm = True

        if door != prev_door:
            ser.write(b"D" if door == 1 else b"C")
        prev_door = door
    
        if armed != prev_armed:
            prev_armed = armed
            client.publish(STATE_TOPIC, json.dumps({"timestamp": int(time.time()), "armed": armed,}), 1, True)
            print("→ state", armed)

        if alarm != prev_alarm:
            prev_alarm = alarm
            client.publish(EVENT_TOPIC, json.dumps({"timestamp": int(time.time()), "alarm": alarm, "alarm_code": "anomaly" if alarm else "normal",}), 1, False)
            print("→ event", alarm)

        print(f"armed {armed}, alarm {alarm}")

        if door == 1:
            print("door_state = open")
        else:
            print("door_state = close")

        if data is None:
            print("...沒收到完整資料")
        else:
            last_pico = data
            print(f"距離 {data.get('dist_mm', '?')} mm, 狀態 {data.get('state', '?')}, 門 {data.get('door', '?')}")
except KeyboardInterrupt:
    print("\n結束中...")

if mqtt_ok:
    client.publish(TOPIC, json.dumps({"online": False}), 1, True)
time.sleep(0.5)
client.loop_stop()
client.disconnect()
ser.close()