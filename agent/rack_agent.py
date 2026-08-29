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

CODE_NONE = "NONE"
CODE_DOOR = "UNAUTHORIZED_DOOR_OPEN"
CODE_APPROACH = "UNAUTHORIZED_APPROCH"

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
    global armed, alarm, alarm_code

    payload = json.loads(msg.payload.decode())
    action = payload["action"]

    if action == "ARM":
        armed = True
    elif action == "DISARM":
        armed = False
    elif action == "RESET_ALARM":
        alarm = False
        alarm_code = CODE_NONE

def on_connect(client, userdata, connect_flags, reason_code, properties):
    global prev_armed, prev_alarm

    if reason_code != 0:
        print(f"▲ MQTT 連線被拒: {reason_code}")
        return
    
    print("MQTT 已連線，重新同步狀態")

    client.subscribe(CMD_TOPIC, 1)
    client.publish(TOPIC, json.dumps({"online": True}), 1, True)

    prev_armed = None      
    prev_alarm = None

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    print(f"▲ MQTT 已斷線 (reason_code={reason_code})，背景自動重連中")

if not os.path.exists(DEVICE_PATH):
    print(f"x 找不到 {DEVICE_PATH}")
    print("  核心模組未載入。請先執行:")
    print("  sudo modprobe rack_door")
    raise SystemExit(1)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rack-security")

client.on_connect = on_connect
client.on_message = on_cmd
client.on_disconnect = on_disconnect

client.will_set(TOPIC, json.dumps({"online": False}), 1, True)

client.reconnect_delay_set(min_delay=1, max_delay=30)
client.connect_async(BROKER, PORT, 60)
client.loop_start()

ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
ser.reset_input_buffer()

last_pico = None

armed = True
alarm = False
alarm_code = CODE_NONE
prev_door = read_door()
ser.write(b"D" if prev_door == 1 else b"C")
prev_armed = None
prev_alarm = False
prev_pico_state = "normal"

last_telemetry = 0.0
prev_online = None

try:
    while True:
        door = read_door()
        data = read_pico()
        now = time.time()

        if data is not None:
            last_pico = data

        if last_pico is None:
            pico_state = "error"
        else:
            pico_state = STATE_NAME.get(last_pico["state"], "error")

        if now - last_telemetry >= TELEMETRY_INTERVAL:
            last_telemetry = now

            payload = {
                "timestamp": int(now),
                "status": "nominal" if (pico_state == "normal" and door == 0) else "anomaly",
                "pico_state": pico_state,
                "door_rack": "open" if door == 1 else "close",
            }

            client.publish(TELEMETRY_TOPIC, json.dumps(payload), 0, False)
            print("→ telemetry", payload)

        door_opened = (door == 1 and prev_door == 0)
        intruder_near = (pico_state == "alert" and prev_pico_state != "alert")

        if armed and not alarm:
            if door_opened:
                alarm = True
                alarm_code = CODE_DOOR
            elif intruder_near:
                alarm = True
                alarm_code = CODE_APPROACH

        if door != prev_door:
            ser.write(b"D" if door == 1 else b"C")
        prev_door = door
        prev_pico_state = pico_state
    
        if armed != prev_armed:
            prev_armed = armed
            client.publish(STATE_TOPIC, json.dumps({
                "timestamp": int(now),
                "armed": armed,
            }), 1, True)
            print("→ state", armed)

        if alarm != prev_alarm:
            prev_alarm = alarm
            client.publish(EVENT_TOPIC, json.dumps({
                "timestamp": int(now),
                "alarm": alarm,
                "alarm_code": alarm_code,
            }), 1, False)
            print("→ event", alarm, alarm_code)

        online = client.is_connected()
        if online != prev_online:
            prev_online = online
            print("MQTT 連線狀態:", "已連線" if online else "離線 (本地判斷持續運作)")

        print(f"armed {armed}, alarm {alarm}, code {alarm_code}")

        if door == 1:
            print("door_state = open")
        else:
            print("door_state = close")

        if data is None:
            print("...沒收到完整資料")
        else:
            print(f"距離 {data.get('dist_mm', '?')} mm, 狀態 {data.get('state', '?')}, 門 {data.get('door', '?')}")
except KeyboardInterrupt:
    print("\n結束中...")

if client.is_connected():
    client.publish(TOPIC, json.dumps({"online": False}), 1, True)
    time.sleep(0.5)

client.loop_stop()
client.disconnect()
ser.close()