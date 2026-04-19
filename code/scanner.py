"""
scanner.py — Spectrum / RSSI Scanner
Sweeps a frequency range and prints a live bar-graph to USB serial.
"""

import time


class Scanner:
    def __init__(self, radio):
        self.radio = radio

    def scan_range(self, start_mhz=300.0, end_mhz=928.0, step_mhz=1.0,
                   dwell_ms=5, threshold_dbm=-80):
        """
        Sweep start_mhz → end_mhz in step_mhz increments.
        Prints a live RSSI bar chart to the terminal.
        Press Ctrl-C to stop.
        """
        print("\n╔══════════════════════════════════════════════════════╗")
        print("║          RF SPECTRUM SCANNER                         ║")
        print("╠══════════════════════════════════════════════════════╣")
        print(f"║  Range : {start_mhz:.1f} – {end_mhz:.1f} MHz              ║")
        print(f"║  Step  : {step_mhz:.1f} MHz                               ║")
        print(f"║  Dwell : {dwell_ms} ms/step                              ║")
        print("║  Press Ctrl-C to stop                                ║")
        print("╚══════════════════════════════════════════════════════╝\n")

        hotspots = []

        try:
            freq = start_mhz
            while freq <= end_mhz:
                self.radio.set_freq_mhz(freq)
                self.radio.rx_mode()
                time.sleep_ms(dwell_ms)
                rssi = self.radio.get_rssi_dbm()
                self.radio.idle()

                bar_len = max(0, int((rssi + 110) / 2))
                bar = "█" * bar_len
                flag = " ◄ SIGNAL!" if rssi > threshold_dbm else ""

                print(f"  {freq:7.2f} MHz │{bar:<30}│ {rssi:+.1f} dBm{flag}")

                if rssi > threshold_dbm:
                    hotspots.append((freq, rssi))

                freq = round(freq + step_mhz, 3)

        except KeyboardInterrupt:
            pass

        self.radio.idle()
        self._print_hotspots(hotspots)
        return hotspots

    def scan_channels(self, channels_mhz, dwell_ms=10):
        """
        Scan a specific list of frequencies (e.g. common ISM channels).
        Returns dict {freq: rssi}.
        """
        results = {}
        for freq in channels_mhz:
            self.radio.set_freq_mhz(freq)
            self.radio.rx_mode()
            time.sleep_ms(dwell_ms)
            rssi = self.radio.get_rssi_dbm()
            self.radio.idle()
            results[freq] = rssi
        return results

    def monitor_freq(self, freq_mhz=433.92, duration_s=30, interval_ms=200):
        """
        Monitor a single frequency over time — good for watching traffic bursts.
        """
        print(f"\n📡  Monitoring {freq_mhz} MHz for {duration_s}s")
        print(f"{'Time':>8}  {'RSSI':>7}  Signal")
        print("-" * 50)

        self.radio.set_freq_mhz(freq_mhz)
        start = time.time()
        peak = -120.0

        try:
            while (time.time() - start) < duration_s:
                self.radio.rx_mode()
                time.sleep_ms(interval_ms)
                rssi = self.radio.get_rssi_dbm()
                self.radio.idle()
                elapsed = time.time() - start
                peak = max(peak, rssi)

                bar = "▐" * max(0, int((rssi + 110) / 3))
                print(f"{elapsed:7.1f}s  {rssi:+6.1f}  {bar}")

        except KeyboardInterrupt:
            pass

        print(f"\n  Peak RSSI: {peak:+.1f} dBm")
        self.radio.idle()
        return peak

    def quick_scan(self):
        """Scan common ISM / remote-control bands and report."""
        channels = {
            "315.00 MHz (US remotes)":    315.00,
            "433.92 MHz (EU remotes)":    433.92,
            "434.42 MHz (alt)":           434.42,
            "868.00 MHz (EU LoRa)":       868.00,
            "868.35 MHz (EU)":            868.35,
            "915.00 MHz (US LoRa)":       915.00,
        }
        print("\n📡  Quick ISM Band Scan")
        print(f"{'Channel':<30} {'RSSI':>8}  Activity")
        print("-" * 55)

        results = {}
        for name, freq in channels.items():
            self.radio.set_freq_mhz(freq)
            self.radio.rx_mode()
            time.sleep_ms(15)
            rssi = self.radio.get_rssi_dbm()
            self.radio.idle()
            activity = "ACTIVE" if rssi > -85 else "quiet"
            print(f"  {name:<28} {rssi:+6.1f} dBm  {activity}")
            results[name] = rssi

        return results

    def _print_hotspots(self, hotspots):
        if not hotspots:
            print("\n  No signals detected above threshold.")
            return
        print(f"\n  ── Hotspots detected: {len(hotspots)} ──")
        for freq, rssi in sorted(hotspots, key=lambda x: -x[1]):
            print(f"    {freq:.2f} MHz → {rssi:+.1f} dBm")
