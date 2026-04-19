"""
sniffer.py — Protocol Sniffer & Decoder
Decodes common sub-GHz protocols: OOK/PT2262, Manchester, raw FSK packets.
"""

import time


# ── Pulse-level decoders ──────────────────────────────────────────────────────

def decode_ook_pt2262(pulses, tolerance=0.35):
    """
    Decode PT2262 / EV1527-style OOK.
    Returns (bits_str, address, command) or None.
    Timing: short=~350µs, long=~1050µs (3:1 ratio), sync ~10500µs.
    """
    if len(pulses) < 24:
        return None

    # Find sync (long low pulse > 5ms)
    sync_idx = None
    for i, p in enumerate(pulses):
        if p > 5000:
            sync_idx = i
            break

    if sync_idx is None:
        # Try from start
        sync_idx = 0

    pulses = pulses[sync_idx + 1:]

    if len(pulses) < 24:
        return None

    # Estimate unit time from first pulse pair
    if len(pulses) >= 2:
        unit = (pulses[0] + pulses[1]) / 4
    else:
        return None

    if unit < 50 or unit > 2000:
        return None

    bits = []
    i = 0
    while i + 1 < len(pulses) and len(bits) < 24:
        hi = pulses[i]
        lo = pulses[i + 1]
        if abs(hi - unit) < unit * tolerance and abs(lo - 3 * unit) < 3 * unit * tolerance:
            bits.append('0')
        elif abs(hi - 3 * unit) < 3 * unit * tolerance and abs(lo - unit) < unit * tolerance:
            bits.append('1')
        else:
            break
        i += 2

    if len(bits) < 12:
        return None

    bits_str = "".join(bits)
    addr_bits = bits_str[:20] if len(bits_str) >= 24 else bits_str[:-4]
    cmd_bits  = bits_str[-4:] if len(bits_str) >= 24 else "????"
    addr = int(addr_bits, 2) if addr_bits.replace('0','').replace('1','') == '' else None
    cmd  = int(cmd_bits,  2) if cmd_bits.replace('0','').replace('1','')  == '' else None

    return {"bits": bits_str, "address": addr, "command": cmd, "protocol": "PT2262/EV1527"}


def decode_manchester(pulses, unit_us=500, tolerance=0.4):
    """
    Decode Manchester-encoded signal.
    Returns bit string or None.
    """
    bits = []
    i = 0
    half = unit_us
    full = unit_us * 2

    while i < len(pulses):
        p = pulses[i]
        if abs(p - half) < half * tolerance:
            # Short pulse — half bit
            if i + 1 < len(pulses) and abs(pulses[i+1] - half) < half * tolerance:
                # Two shorts = one bit
                bits.append('1' if i % 2 == 0 else '0')
                i += 2
            else:
                i += 1
        elif abs(p - full) < full * tolerance:
            # Long pulse = transition
            bits.append('0' if i % 2 == 0 else '1')
            i += 1
        else:
            i += 1

    return "".join(bits) if len(bits) >= 4 else None


def pulses_to_binary(pulses, threshold_us=None):
    """Convert raw pulses to binary string using threshold."""
    if not pulses:
        return ""
    if threshold_us is None:
        avg = sum(pulses) / len(pulses)
        threshold_us = avg
    return "".join('1' if p >= threshold_us else '0' for p in pulses)


# ── High-level sniffer ────────────────────────────────────────────────────────

class Sniffer:
    def __init__(self, radio):
        self.radio = radio
        self.history = []

    def sniff(self, freq_mhz=433.92, duration_s=30, auto_decode=True):
        """
        Listen on freq_mhz and decode any OOK signals detected.
        Runs for duration_s seconds or until Ctrl-C.
        """
        print(f"\n🕵️   Protocol Sniffer — {freq_mhz} MHz")
        print(f"    Duration: {duration_s}s  |  Press Ctrl-C to stop early")
        print("-" * 55)

        self.radio.set_freq_mhz(freq_mhz)
        start = time.time()
        pkt_count = 0

        try:
            while (time.time() - start) < duration_s:
                # Wait for signal activity (RSSI above noise floor)
                self.radio.rx_mode()
                time.sleep_ms(5)
                rssi = self.radio.get_rssi_dbm()

                if rssi > -85:
                    # Capture the burst
                    pulses, start_level = self.radio.capture_raw(
                        timeout_ms=300, max_edges=512
                    )
                    self.radio.idle()

                    if len(pulses) < 8:
                        continue

                    pkt_count += 1
                    ts = time.time() - start
                    print(f"\n  [{ts:6.1f}s] Signal #{pkt_count} — RSSI {rssi:+.1f} dBm — {len(pulses)} edges")

                    if auto_decode:
                        self._try_decode(pulses, start_level)

                    self.history.append({
                        "time_s":     ts,
                        "freq_mhz":   freq_mhz,
                        "rssi":       rssi,
                        "pulses":     pulses,
                        "start_level": start_level,
                    })
                else:
                    self.radio.idle()
                    time.sleep_ms(20)

        except KeyboardInterrupt:
            pass

        self.radio.idle()
        print(f"\n  ── Sniffer done. {pkt_count} packets captured ──")
        return self.history

    def sniff_fsk_packets(self, freq_mhz=433.92, baud=4800, duration_s=30):
        """
        Sniff FSK data packets (e.g., weather stations, sensors).
        Prints raw hex of received packets.
        """
        from cc1101 import MOD_2FSK
        print(f"\n🕵️   FSK Packet Sniffer — {freq_mhz} MHz @ {baud} baud")
        print(f"    Duration: {duration_s}s")
        print("-" * 55)

        self.radio.set_freq_mhz(freq_mhz)
        self.radio.set_modulation(MOD_2FSK)
        self.radio.set_datarate(baud)
        self.radio.set_bandwidth(200)
        self.radio.set_packet_mode(variable=True)
        self.radio.set_sync_mode(2)

        start = time.time()
        pkt_count = 0

        try:
            while (time.time() - start) < duration_s:
                pkt = self.radio.receive_packet(timeout_ms=500)
                if pkt and len(pkt) > 0:
                    pkt_count += 1
                    ts = time.time() - start
                    hex_str = " ".join(f"{b:02X}" for b in pkt)
                    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in pkt)
                    print(f"\n  [{ts:6.1f}s] Packet #{pkt_count} ({len(pkt)} bytes)")
                    print(f"    HEX  : {hex_str}")
                    print(f"    ASCII: {ascii_str}")

        except KeyboardInterrupt:
            pass

        self.radio.idle()
        print(f"\n  ── Done. {pkt_count} packets received ──")

    def sniff_multi_channel(self, channels_mhz, hop_ms=50, duration_s=60):
        """
        Hop between multiple frequencies and log activity.
        Useful for finding traffic across common ISM bands.
        """
        print(f"\n🕵️   Multi-Channel Sniffer — {len(channels_mhz)} channels")
        print(f"    Channels: {channels_mhz}")
        print("-" * 55)

        start = time.time()
        activity = {ch: [] for ch in channels_mhz}

        try:
            while (time.time() - start) < duration_s:
                for freq in channels_mhz:
                    self.radio.set_freq_mhz(freq)
                    self.radio.rx_mode()
                    time.sleep_ms(hop_ms)
                    rssi = self.radio.get_rssi_dbm()
                    self.radio.idle()

                    if rssi > -85:
                        ts = time.time() - start
                        activity[freq].append((ts, rssi))
                        print(f"  [{ts:6.1f}s] {freq:.2f} MHz — RSSI {rssi:+.1f} dBm ◄ ACTIVE")

        except KeyboardInterrupt:
            pass

        self.radio.idle()
        print("\n  ── Activity summary ──")
        for freq, events in activity.items():
            print(f"  {freq:.2f} MHz : {len(events)} events")
        return activity

    def print_history(self):
        if not self.history:
            print("  No packets in history.")
            return
        print(f"\n  Packet history ({len(self.history)} entries):")
        for i, h in enumerate(self.history):
            print(f"  [{i:3d}] t={h['time_s']:.1f}s  {h['freq_mhz']}MHz  "
                  f"RSSI={h['rssi']:+.1f}  edges={len(h['pulses'])}")

    def _try_decode(self, pulses, start_level):
        # Try PT2262
        result = decode_ook_pt2262(pulses)
        if result:
            print(f"    ✓ PT2262/EV1527 → addr={result['address']}  cmd={result['command']}  bits={result['bits']}")
            return

        # Try Manchester
        man = decode_manchester(pulses)
        if man and len(man) >= 8:
            print(f"    ✓ Manchester → bits={man[:32]}{'...' if len(man)>32 else ''}")
            return

        # Raw binary
        raw = pulses_to_binary(pulses)
        if raw:
            print(f"    ? Unknown → raw bits={raw[:32]}{'...' if len(raw)>32 else ''}")
