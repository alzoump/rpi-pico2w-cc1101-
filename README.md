# rpi-pico2w-cc1101

Spectrum Analyzer, Capture & Replay, Protocol Sniffer, and Radio Information Tool using Raspberry Pi Pico 2W and CC1101.

---

## 🔧 Hardware Required
- Raspberry Pi Pico 2W
- CC1101 wireless transceiver module
- Jumper wires

## ⚡ Wiring

| CC1101 Pin | Pico 2W Pin |
|------------|-------------|
| VCC        | 3.3V        |
| GND        | GND         |
| MOSI       | GP19        |
| MISO       | GP16        |
| SCK        | GP18        |
| CSN        | GP17        |
| GDO0       | GP20        |


## Setup Instructions

### Step 1 — Flash the firmware
Plug the Raspberry Pi Pico 2W into your PC **while holding the BOOT button**.

### Step 2 — Create a project
Open PyCharm and create a new project using **Python 3.11**.

### Step 3 — Download MicroPython
Run this in PyCharm's terminal:
```powershell
Invoke-WebRequest -Uri "https://micropython.org/resources/firmware/RPI_PICO2_W-20250415-v1.25.0.uf2" -OutFile pico_firmware.uf2
```

### Step 4 — Install mpremote
```powershell
pip install mpremote
```

### Step 5 — Connect the Pico
Check if the Pico is visible:
```powershell
mpremote connect list
```
If it is not detected, copy the firmware to the Pico:
```powershell
copy pico_firmware.uf2 D:\
```
> **Note:** Replace `D:\` with the correct drive letter if your Pico shows up differently.

### Step 6 — Add project files
Drag and drop all Python files into your PyCharm project.

### Step 7 — Upload files to the Pico
Replace `COM16` with your actual COM port, then run:
```powershell
mpremote connect COM16 cp cc1101.py :cc1101.py
mpremote connect COM16 cp scanner.py :scanner.py
mpremote connect COM16 cp capture.py :capture.py
mpremote connect COM16 cp sniffer.py :sniffer.py
mpremote connect COM16 cp main.py :main.py
```

### Step 8 — Start the REPL
```powershell
mpremote connect COM16 repl
```

### Step 9 — Run the program
Once you see:
