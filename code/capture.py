"""
capture.py — OOK/ASK Signal Capture & Replay (Flipper Zero-like)
Captures raw pulse timings from GDO0, stores them, replays on command.
"""

import time
import json


class Capture:
    def __init__(self, radio):
        self.radio = radio
        self.library = {}   # name → {pulses, start_level, freq_mhz}

    # ── Capture ───────────────────────────────────────────────────────────────

    def record(self, freq_mhz=433.92, name=None, timeout_ms=3000,
               min_pulse_us=100, noise_filter_us=50):
        """
        Listen on freq_mhz and capture an OOK/ASK signal.
        Waits for activity then records until silence.
        Returns signal dict or None on timeout.
        """
        if name is None:
            name = f"sig_{int(time.time())}"

        print(f"\n🔴  Recording '{name}' on {freq_mhz} MHz")
        print(f"    Timeout: {timeout_ms}ms  |  Point the remote at the antenna and press the button.")
        print("    Waiting for signal...")

        self.radio.set_freq_mhz(freq_mhz)

        # Wait for signal activity first
        print("    Waiting for activity (watching RSSI)...")
        from cc1101 import MOD_ASK
        self.radio.set_modulation(MOD_ASK)
        self.radio.rx_mode()
        deadline = __import__('time').ticks_add(__import__('time').ticks_ms(), timeout_ms)
        import time
        while True:
            rssi = self.radio.get_rssi_dbm()
            if rssi > -70:
                print(f"    Signal detected! RSSI={rssi:+.1f} dBm — capturing...")
                break
            if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                print("    ✗ Timeout waiting for signal.")
                self.radio.idle()
                return None
            time.sleep_ms(10)

        pulses, start_level = self.radio.capture_raw(
            timeout_ms=timeout_ms, max_edges=1024
        )

        if len(pulses) < 4:
            print("    ✗ No signal detected.")
            return None

        # Filter noise
        pulses = [p for p in pulses if p > noise_filter_us]

        # Trim long silences at start/end (>50ms)
        while pulses and pulses[0] > 50_000:
            pulses = pulses[1:]
            start_level ^= 1
        while pulses and pulses[-1] > 50_000:
            pulses = pulses[:-1]

        sig = {
            "name":        name,
            "freq_mhz":    freq_mhz,
            "start_level": start_level,
            "pulses":      pulses,
            "edge_count":  len(pulses),
            "duration_ms": sum(pulses) // 1000,
        }

        self.library[name] = sig
        self._print_signal_info(sig)
        return sig

    def replay(self, name, repeat=3, gap_ms=50):
        """Replay a captured signal by name."""
        if name not in self.library:
            print(f"  ✗ Signal '{name}' not found. Library: {list(self.library.keys())}")
            return False

        sig = self.library[name]
        print(f"\n▶️   Replaying '{name}' × {repeat} on {sig['freq_mhz']} MHz")

        self.radio.set_freq_mhz(sig["freq_mhz"])
        self.radio.replay_raw(
            sig["pulses"],
            start_level=sig["start_level"],
            repeat=repeat,
            gap_ms=gap_ms
        )
        print("    ✓ Done.")
        return True

    def replay_signal(self, sig, repeat=3, gap_ms=50):
        """Replay a signal dict directly."""
        self.radio.set_freq_mhz(sig["freq_mhz"])
        self.radio.replay_raw(
            sig["pulses"],
            start_level=sig["start_level"],
            repeat=repeat,
            gap_ms=gap_ms
        )

    # ── Library management ────────────────────────────────────────────────────

    def list_signals(self):
        if not self.library:
            print("  Library is empty.")
            return
        print(f"\n📂  Saved signals ({len(self.library)}):")
        print(f"  {'Name':<20} {'Freq':>8}  {'Edges':>6}  {'Duration':>10}")
        print("  " + "-" * 50)
        for name, sig in self.library.items():
            print(f"  {name:<20} {sig['freq_mhz']:>7.2f}  {sig['edge_count']:>6}  {sig['duration_ms']:>8}ms")

    def delete(self, name):
        if name in self.library:
            del self.library[name]
            print(f"  Deleted '{name}'.")
        else:
            print(f"  Signal '{name}' not found.")

    def save_to_file(self, filename="signals.json"):
        """Save library to JSON file on the Pico's flash."""
        try:
            with open(filename, "w") as f:
                json.dump(self.library, f)
            print(f"  ✓ Saved {len(self.library)} signals to {filename}")
        except Exception as e:
            print(f"  ✗ Save failed: {e}")

    def load_from_file(self, filename="signals.json"):
        """Load library from JSON file."""
        try:
            with open(filename) as f:
                self.library = json.load(f)
            print(f"  ✓ Loaded {len(self.library)} signals from {filename}")
        except OSError:
            print(f"  ℹ  No saved signals found ({filename})")
        except Exception as e:
            print(f"  ✗ Load failed: {e}")

    def export_signal(self, name):
        """Print a signal as a compact string for copy-paste."""
        if name not in self.library:
            print(f"  ✗ '{name}' not found.")
            return
        sig = self.library[name]
        print(f"\n  Export: {name}")
        print(f"  Freq: {sig['freq_mhz']} MHz")
        print(f"  Start: {sig['start_level']}")
        print(f"  Pulses: {sig['pulses']}")

    # ── Analysis ──────────────────────────────────────────────────────────────

    def analyze(self, name):
        """Basic analysis: detect likely encoding (OOK/PT2262 style)."""
        if name not in self.library:
            print(f"  ✗ '{name}' not found.")
            return
        sig = self.library[name]
        pulses = sig["pulses"]

        if not pulses:
            print("  Empty pulse list.")
            return

        # Find short and long pulses (bi-level OOK)
        filtered = [p for p in pulses if 50 < p < 20_000]
        if not filtered:
            print("  No valid pulses to analyze.")
            return

        avg = sum(filtered) / len(filtered)
        short = [p for p in filtered if p < avg]
        long_ = [p for p in filtered if p >= avg]

        avg_short = sum(short) / len(short) if short else 0
        avg_long  = sum(long_) / len(long_) if long_ else 0
        ratio = avg_long / avg_short if avg_short > 0 else 0

        print(f"\n  📊 Analysis: '{name}'")
        print(f"     Total edges  : {len(pulses)}")
        print(f"     Avg short    : {avg_short:.0f} µs")
        print(f"     Avg long     : {avg_long:.0f} µs")
        print(f"     Long/Short   : {ratio:.2f}x")
        if 0.9 < ratio < 1.1:
            print("     Likely: Manchester encoding")
        elif 2.5 < ratio < 3.5:
            print("     Likely: PT2262 / OOK (3:1 ratio)")
        elif 1.8 < ratio < 2.2:
            print("     Likely: 2:1 OOK (NEC-style)")
        else:
            print("     Encoding: unknown / custom")

    def _print_signal_info(self, sig):
        print(f"\n  ✓ Captured '{sig['name']}'")
        print(f"     Freq     : {sig['freq_mhz']} MHz")
        print(f"     Edges    : {sig['edge_count']}")
        print(f"     Duration : {sig['duration_ms']} ms")
        if sig["pulses"]:
            print(f"     Min pulse: {min(sig['pulses'])} µs")
            print(f"     Max pulse: {max(sig['pulses'])} µs")

