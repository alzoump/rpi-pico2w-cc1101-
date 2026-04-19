"""
main.py — RF Toolkit for RPi Pico 2W + CC1101
Full RF toolkit: spectrum scanner, OOK capture/replay, protocol sniffer.

Wiring (SPI0):
  CC1101 VCC  → 3.3V (Pin 36)
  CC1101 GND  → GND  (Pin 38)
  CC1101 SCK  → GP18 (Pin 24)
  CC1101 MOSI → GP19 (Pin 25)
  CC1101 MISO → GP16 (Pin 21)
  CC1101 CSN  → GP17 (Pin 22)
  CC1101 GDO0 → GP22 (Pin 29)
"""

import time
from cc1101  import CC1101
from scanner import Scanner
from capture import Capture
from sniffer import Sniffer

# ── Startup ───────────────────────────────────────────────────────────────────

def banner():
    print("\n")
    print("  ╔══════════════════════════════════════╗")
    print("  ║   🔭  RF TOOLKIT  v1.0               ║")
    print("  ║   Pico 2W + CC1101  Sub-GHz Suite    ║")
    print("  ╚══════════════════════════════════════╝")
    print()

def check_radio(radio):
    ver = radio.get_version()
    if ver in (0x14, 0x04, 0x05, 0x06, 0x07):
        print(f"  ✓ CC1101 detected (version=0x{ver:02X})")
        return True
    else:
        print(f"  ✗ CC1101 NOT found (got 0x{ver:02X}) — check wiring!")
        return False

# ── Menus ─────────────────────────────────────────────────────────────────────

def menu_scanner(scanner):
    while True:
        print("\n  ── Scanner Menu ──")
        print("  1. Quick ISM scan (common channels)")
        print("  2. Full sweep (300–928 MHz)")
        print("  3. Custom sweep")
        print("  4. Monitor single frequency")
        print("  0. Back")
        choice = input("\n  > ").strip()

        if choice == "1":
            scanner.quick_scan()

        elif choice == "2":
            step = float(input("  Step (MHz) [default 1.0]: ") or "1.0")
            scanner.scan_range(300, 928, step)

        elif choice == "3":
            start = float(input("  Start MHz: "))
            end   = float(input("  End MHz:   "))
            step  = float(input("  Step MHz [0.5]: ") or "0.5")
            thresh = float(input("  Alert threshold dBm [-80]: ") or "-80")
            scanner.scan_range(start, end, step, threshold_dbm=thresh)

        elif choice == "4":
            freq = float(input("  Frequency MHz [433.92]: ") or "433.92")
            dur  = int(input("  Duration seconds [30]: ")    or "30")
            scanner.monitor_freq(freq, dur)

        elif choice == "0":
            break


def menu_capture(capture):
    while True:
        print("\n  ── Capture & Replay Menu ──")
        print("  1. Record signal")
        print("  2. List saved signals")
        print("  3. Replay signal")
        print("  4. Analyze signal")
        print("  5. Export signal (print pulses)")
        print("  6. Save library to flash")
        print("  7. Load library from flash")
        print("  8. Delete signal")
        print("  0. Back")
        choice = input("\n  > ").strip()

        if choice == "1":
            freq = float(input("  Frequency MHz [433.92]: ") or "433.92")
            name = input("  Name [auto]: ").strip() or None
            timeout = int(input("  Timeout ms [3000]: ") or "3000")
            capture.record(freq, name, timeout)

        elif choice == "2":
            capture.list_signals()

        elif choice == "3":
            capture.list_signals()
            name = input("  Signal name: ").strip()
            rep  = int(input("  Repeat count [3]: ") or "3")
            capture.replay(name, repeat=rep)

        elif choice == "4":
            capture.list_signals()
            name = input("  Signal name: ").strip()
            capture.analyze(name)

        elif choice == "5":
            capture.list_signals()
            name = input("  Signal name: ").strip()
            capture.export_signal(name)

        elif choice == "6":
            capture.save_to_file()

        elif choice == "7":
            capture.load_from_file()

        elif choice == "8":
            capture.list_signals()
            name = input("  Signal name to delete: ").strip()
            capture.delete(name)

        elif choice == "0":
            break


def menu_sniffer(sniffer):
    while True:
        print("\n  ── Protocol Sniffer Menu ──")
        print("  1. OOK/ASK sniffer (auto-decode)")
        print("  2. FSK packet sniffer")
        print("  3. Multi-channel hopper")
        print("  4. Show history")
        print("  0. Back")
        choice = input("\n  > ").strip()

        if choice == "1":
            freq = float(input("  Frequency MHz [433.92]: ") or "433.92")
            dur  = int(input("  Duration seconds [30]: ")    or "30")
            sniffer.sniff(freq, dur)

        elif choice == "2":
            freq = float(input("  Frequency MHz [433.92]: ") or "433.92")
            baud = int(input("  Baud rate [4800]: ")          or "4800")
            dur  = int(input("  Duration seconds [30]: ")     or "30")
            sniffer.sniff_fsk_packets(freq, baud, dur)

        elif choice == "3":
            print("  Enter frequencies separated by commas:")
            raw = input("  [315,433.92,868,915]: ") or "315,433.92,868,915"
            channels = [float(x.strip()) for x in raw.split(",")]
            dur = int(input("  Duration seconds [60]: ") or "60")
            sniffer.sniff_multi_channel(channels, duration_s=dur)

        elif choice == "4":
            sniffer.print_history()

        elif choice == "0":
            break


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    banner()

    print("  Initializing CC1101...")
    radio = CC1101(spi_id=0, sck=18, mosi=19, miso=16, csn=17, gdo0=22)
    time.sleep_ms(100)

    if not check_radio(radio):
        print("  Halting. Fix wiring and reset.")
        return

    scanner = Scanner(radio)
    capture = Capture(radio)
    sniffer = Sniffer(radio)

    # Load any previously saved signals
    capture.load_from_file()

    while True:
        print("\n  ══ Main Menu ══")
        print("  1. 📡  Spectrum Scanner")
        print("  2. 🔴  Capture & Replay (Flipper-style)")
        print("  3. 🕵️   Protocol Sniffer")
        print("  4. ℹ️   Radio info")
        print("  0. Exit")
        choice = input("\n  > ").strip()

        if choice == "1":
            menu_scanner(scanner)
        elif choice == "2":
            menu_capture(capture)
        elif choice == "3":
            menu_sniffer(sniffer)
        elif choice == "4":
            print(f"\n  CC1101 version : 0x{radio.get_version():02X}")
            print(f"  Current freq   : {radio.get_freq_mhz()} MHz")
            print(f"  RSSI           : {radio.get_rssi_dbm():+.1f} dBm")
            print(f"  State          : 0x{radio.get_state():02X}")
        elif choice == "0":
            radio.idle()
            print("  Goodbye.")
            break


main()
