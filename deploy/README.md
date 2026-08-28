# 部署說明

## 相依 repo

kernel module 位於獨立 repo，clone 本 repo 後需另外取得：

    cd ~/Seminar
    git clone git@github.com:a9921/rack-door-kmod.git kmod
    cd kmod && make install

## 架構

    開機 → modules-load.d 載入 rack_door
         → device_create() 建立 /dev/rack_door1
         → udev 規則 TAG+="systemd"
         → dev-rack_door1.device
         → BindsTo 啟動 rack-monitor.service

kmod 卸載時 systemd 自動停止 service，重新載入時 udev 自動拉起。
UART 斷線不由 systemd 處理，交由 agent 的 timeout fallback。

## 安裝

    # 1. 編譯並安裝 kernel module
    cd kmod && make install

    # 2. 設定開機載入
    sudo cp deploy/rack_door.conf /etc/modules-load.d/

    # 3. udev 規則
    sudo cp deploy/99-rack.rules /etc/udev/rules.d/
    sudo udevadm control --reload-rules

    # 4. systemd service
    sudo cp deploy/rack-monitor.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now rack-monitor.service

## 前置需求

- Python 套件：`sudo apt install python3-serial python3-paho-mqtt`
  （Bookworm 有 PEP 668，不要用 pip）
- UART：config.txt 需 `enable_uart=1`，且 `serial-getty@ttyAMA0` 須停用
- 執行使用者需在 `dialout` 群組
- MQTT broker 位址寫在 `agent/rack_agent.py`（目前 192.168.69.190）
- `rack-monitor.service` 內有絕對路徑 `/home/pi/Seminar/agent`，換機器需修改

## 驗證

    lsmod | grep rack_door
    ls -l /dev/rack_door1
    systemctl list-units --type=device | grep rack
    systemctl status rack-monitor.service
    journalctl -u rack-monitor.service -f

BindsTo 機制測試：

    sudo rmmod rack_door      # service 應變為 inactive (dead)
    sudo modprobe rack_door   # service 應自動回到 active

## 排查

由下往上逐層確認：

    lsmod | grep rack_door                          # module 載入了嗎
    ls -l /dev/rack_door1                           # 節點在不在
    udevadm test /sys/devices/virtual/rack1/rack_door1   # udev 規則有比對到嗎
    systemctl list-units --type=device | grep rack  # .device unit 生出來了嗎
    journalctl -u rack-monitor.service -b           # agent 輸出

若 .device unit 沒出現，問題在 udev 的 TAG+="systemd"；
若 unit 存在但 service 不動，檢查裝置名稱在三處是否一致
（device_create、udev KERNEL==、service 的 dev-*.device）。

## 開發流程

修改 rack_door.c 後：

    cd kmod && make reload

`make reload` 會編譯、安裝到 /lib/modules/.../extra/、重新載入，
service 由 udev 自動重啟（中斷約 2 秒）。
切勿只跑 make 後直接 insmod ./rack_door.ko，
否則 extra/ 仍是舊版，重開機後行為與測試不一致。
