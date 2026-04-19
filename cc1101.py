"""
CC1101 Sub-GHz RF Transceiver Driver for MicroPython (Pico 2W)
SPI0: SCK=GP18, MOSI=GP19, MISO=GP16, CSN=GP17
"""

from machine import SPI, Pin
import time

# ── CC1101 Register Map ───────────────────────────────────────────────────────
IOCFG2   = 0x00
IOCFG1   = 0x01
IOCFG0   = 0x02
FIFOTHR  = 0x03
SYNC1    = 0x04
SYNC0    = 0x05
PKTLEN   = 0x06
PKTCTRL1 = 0x07
PKTCTRL0 = 0x08
ADDR     = 0x09
CHANNR   = 0x0A
FSCTRL1  = 0x0B
FSCTRL0  = 0x0C
FREQ2    = 0x0D
FREQ1    = 0x0E
FREQ0    = 0x0F
MDMCFG4  = 0x10
MDMCFG3  = 0x11
MDMCFG2  = 0x12
MDMCFG1  = 0x13
MDMCFG0  = 0x14
DEVIATN  = 0x15
MCSM2    = 0x16
MCSM1    = 0x17
MCSM0    = 0x18
FOCCFG   = 0x19
BSCFG    = 0x1A
AGCCTRL2 = 0x1B
AGCCTRL1 = 0x1C
AGCCTRL0 = 0x1D
WOREVT1  = 0x1E
WOREVT0  = 0x1F
WORCTRL  = 0x20
FREND1   = 0x21
FREND0   = 0x22
FSCAL3   = 0x23
FSCAL2   = 0x24
FSCAL1   = 0x25
FSCAL0   = 0x26
RCCTRL1  = 0x27
RCCTRL0  = 0x28
FSTEST   = 0x29
PTEST    = 0x2A
AGCTEST  = 0x2B
TEST2    = 0x2C
TEST1    = 0x2D
TEST0    = 0x2E

# Status registers (read-only, add 0x40 burst bit + 0x80 read bit)
PARTNUM   = 0x30
VERSION   = 0x31
FREQEST   = 0x32
LQI       = 0x33
RSSI      = 0x34
MARCSTATE = 0x35
WORTIME1  = 0x36
WORTIME0  = 0x37
PKTSTATUS = 0x38
VCO_VC_DAC = 0x39
TXBYTES   = 0x3A
RXBYTES   = 0x3B

# FIFO
RXFIFO   = 0x3F
TXFIFO   = 0x3F

# Command strobes
SRES     = 0x30
SFSTXON  = 0x31
SXOFF    = 0x32
SCAL     = 0x33
SRX      = 0x34
STX      = 0x35
SIDLE    = 0x36
SWOR     = 0x38
SPWD     = 0x39
SFRX     = 0x3A
SFTX     = 0x3B
SWORRST  = 0x3C
SNOP     = 0x3D

# Modulation modes
MOD_2FSK  = 0x00
MOD_GFSK  = 0x10
MOD_ASK   = 0x30
MOD_4FSK  = 0x40
MOD_MSK   = 0x70

# MARCSTATE values
MARC_IDLE    = 0x01
MARC_RX      = 0x0D
MARC_TX      = 0x13
MARC_RXFIFO  = 0x11


class CC1101:
    def __init__(self, spi_id=0, sck=18, mosi=19, miso=16, csn=17, gdo0=22):
        self.spi = SPI(spi_id, baudrate=4_000_000, polarity=0, phase=0,
                       sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))
        self.cs  = Pin(csn, Pin.OUT, value=1)
        self.gdo0 = Pin(gdo0, Pin.IN)
        self._reset()
        self._default_config()

    # ── Low-level SPI ─────────────────────────────────────────────────────────

    def _select(self):
        self.cs.value(0)
        time.sleep_us(2)

    def _deselect(self):
        time.sleep_us(2)
        self.cs.value(1)

    def _write_reg(self, addr, val):
        self._select()
        self.spi.write(bytes([addr & 0x3F, val]))
        self._deselect()

    def _read_reg(self, addr):
        self._select()
        buf = bytearray(2)
        self.spi.write_readinto(bytes([addr | 0x80, 0x00]), buf)
        self._deselect()
        return buf[1]

    def _read_status(self, addr):
        self._select()
        buf = bytearray(2)
        self.spi.write_readinto(bytes([addr | 0xC0, 0x00]), buf)
        self._deselect()
        return buf[1]

    def _strobe(self, cmd):
        self._select()
        self.spi.write(bytes([cmd]))
        self._deselect()
        time.sleep_us(100)

    def _burst_read(self, addr, n):
        self._select()
        buf = bytearray(n + 1)
        self.spi.write_readinto(bytes([addr | 0xC0]) + bytes(n), buf)
        self._deselect()
        return buf[1:]

    # ── Chip control ──────────────────────────────────────────────────────────

    def _reset(self):
        self.cs.value(0); time.sleep_us(10)
        self.cs.value(1); time.sleep_us(40)
        self._strobe(SRES)
        time.sleep_ms(10)

    def get_version(self):
        return self._read_status(VERSION)

    def idle(self):
        self._strobe(SIDLE)
        time.sleep_us(100)

    def rx_mode(self):
        self.idle()
        self._strobe(SFRX)
        self._strobe(SRX)

    def tx_mode(self):
        self.idle()
        self._strobe(SFTX)
        self._strobe(STX)

    def flush_rx(self):
        self.idle()
        self._strobe(SFRX)

    def flush_tx(self):
        self.idle()
        self._strobe(SFTX)

    def get_state(self):
        return self._read_status(MARCSTATE) & 0x1F

    # ── Frequency ─────────────────────────────────────────────────────────────

    def set_freq_mhz(self, mhz):
        """Set carrier frequency in MHz (300–928)."""
        freq = int(mhz * 1_000_000 / (26_000_000 / 65536))
        self._write_reg(FREQ2, (freq >> 16) & 0xFF)
        self._write_reg(FREQ1, (freq >>  8) & 0xFF)
        self._write_reg(FREQ0,  freq        & 0xFF)

    def get_freq_mhz(self):
        f2 = self._read_reg(FREQ2)
        f1 = self._read_reg(FREQ1)
        f0 = self._read_reg(FREQ0)
        freq = (f2 << 16) | (f1 << 8) | f0
        return round(freq * 26_000_000 / 65536 / 1_000_000, 4)

    # ── RSSI ──────────────────────────────────────────────────────────────────

    def get_rssi_raw(self):
        return self._read_status(RSSI)

    def get_rssi_dbm(self):
        raw = self.get_rssi_raw()
        if raw >= 128:
            return (raw - 256) / 2 - 74
        else:
            return raw / 2 - 74

    # ── Modulation / bandwidth ────────────────────────────────────────────────

    def set_modulation(self, mod=MOD_2FSK):
        val = self._read_reg(MDMCFG2) & 0x8F
        self._write_reg(MDMCFG2, val | mod)

    def set_bandwidth(self, bw_khz=200):
        """Approximate channel filter BW. Common: 58, 100, 200, 325, 406, 812 kHz."""
        table = {
            58:  (3, 3), 68: (3, 2), 81: (3, 1), 101: (3, 0),
            116: (2, 3), 135: (2, 2), 162: (2, 1), 203: (2, 0),
            232: (1, 3), 270: (1, 2), 325: (1, 1), 406: (1, 0),
            464: (0, 3), 541: (0, 2), 650: (0, 1), 812: (0, 0),
        }
        closest = min(table, key=lambda x: abs(x - bw_khz))
        e, m = table[closest]
        val = self._read_reg(MDMCFG4) & 0x0F
        self._write_reg(MDMCFG4, val | (e << 6) | (m << 4))

    def set_datarate(self, baud=4800):
        """Set symbol rate (approx). Common: 1200, 2400, 4800, 9600, 38400."""
        import math
        e = int(math.log2(baud * 2**20 / 26_000_000))
        if e < 0: e = 0
        if e > 15: e = 15
        m = int(round(baud * 2**(28 - e) / 26_000_000 - 256))
        if m > 255: m = 255
        if m < 0:  m = 0
        self._write_reg(MDMCFG4, (self._read_reg(MDMCFG4) & 0xF0) | (e & 0x0F))
        self._write_reg(MDMCFG3, m & 0xFF)

    # ── Packet config ─────────────────────────────────────────────────────────

    def set_packet_mode(self, variable=True):
        if variable:
            self._write_reg(PKTCTRL0, 0x05)  # variable length, CRC on
        else:
            self._write_reg(PKTCTRL0, 0x00)  # fixed length, no CRC

    def set_packet_length(self, length):
        self._write_reg(PKTLEN, length & 0xFF)

    def set_sync_word(self, sync1=0xD3, sync0=0x91):
        self._write_reg(SYNC1, sync1)
        self._write_reg(SYNC0, sync0)

    def set_sync_mode(self, mode=2):
        """0=no sync, 2=16-bit sync, 3=30-of-32 bits."""
        val = self._read_reg(MDMCFG2) & 0xF8
        self._write_reg(MDMCFG2, val | (mode & 0x07))

    # ── RX / TX ───────────────────────────────────────────────────────────────

    def rx_bytes_available(self):
        return self._read_status(RXBYTES) & 0x7F

    def read_rx_fifo(self, n):
        return self._burst_read(RXFIFO | 0x40, n)

    def send_packet(self, data: bytes, timeout_ms=500):
        self.idle()
        self.flush_tx()
        self._select()
        self.spi.write(bytes([TXFIFO | 0x40]) + bytes([len(data)]) + data)
        self._deselect()
        self.tx_mode()
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while self.get_state() == MARC_TX:
            if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                self.idle()
                return False
            time.sleep_us(100)
        return True

    def receive_packet(self, timeout_ms=2000):
        self.rx_mode()
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while True:
            avail = self.rx_bytes_available()
            if avail > 0:
                length = self._read_status(RXBYTES) & 0x7F
                if length == 0:
                    continue
                data = self.read_rx_fifo(length)
                self.flush_rx()
                return bytes(data)
            if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                return None
            time.sleep_us(200)

    # ── Raw OOK capture (GDO0 pin timing) ────────────────────────────────────

    def capture_raw(self, timeout_ms=500, max_edges=512):
        """
        Capture OOK/ASK signal as a list of pulse durations (microseconds).
        Returns (pulses: list[int], start_level: int).
        """
        self.set_modulation(MOD_ASK)
        self.set_bandwidth(200)
        self._write_reg(IOCFG0, 0x0D)   # GDO0 = async serial data out
        self.rx_mode()

        pulses = []
        last = time.ticks_us()
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        level = self.gdo0.value()
        start_level = level

        while len(pulses) < max_edges:
            now_level = self.gdo0.value()
            if now_level != level:
                now = time.ticks_us()
                pulses.append(time.ticks_diff(now, last))
                last = now
                level = now_level
            if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                break

        self.idle()
        return pulses, start_level

    def replay_raw(self, pulses, start_level=0, repeat=3, gap_ms=10):
        """
        Replay a captured OOK/ASK pulse sequence via GDO0 (async TX).
        NOTE: True OOK replay needs an RF switch or direct PA control.
        This outputs the digital pattern on GDO0 for testing / external PA use.
        """
        out = Pin(self.gdo0.id(), Pin.OUT)
        self.set_modulation(MOD_ASK)
        self._write_reg(IOCFG0, 0x2E)   # GDO0 = HiZ (drive manually)
        self.tx_mode()

        for _ in range(repeat):
            level = start_level
            for duration in pulses:
                out.value(level)
                time.sleep_us(duration)
                level ^= 1
            out.value(0)
            time.sleep_ms(gap_ms)

        self.idle()
        # Restore GDO0 as input
        self.gdo0 = Pin(self.gdo0.id(), Pin.IN)

    # ── Default config ────────────────────────────────────────────────────────

    def _default_config(self):
        """Sensible defaults: 433.92 MHz, OOK/ASK, 4.8kbps, 200kHz BW."""
        self._write_reg(IOCFG0,   0x06)   # GDO0 = sync word
        self._write_reg(IOCFG2,   0x0B)   # GDO2 = serial clock
        self._write_reg(FIFOTHR,  0x47)   # RX FIFO threshold 48 bytes
        self._write_reg(PKTCTRL0, 0x00)   # Fixed length, no CRC
        self._write_reg(PKTLEN,   0x3D)   # 61 bytes
        self._write_reg(FSCTRL1,  0x06)
        self._write_reg(AGCCTRL2, 0x43)
        self._write_reg(AGCCTRL1, 0x49)
        self._write_reg(AGCCTRL0, 0x91)
        self._write_reg(FSCAL3,   0xE9)
        self._write_reg(FSCAL2,   0x2A)
        self._write_reg(FSCAL1,   0x00)
        self._write_reg(FSCAL0,   0x1F)
        self._write_reg(TEST2,    0x81)
        self._write_reg(TEST1,    0x35)
        self._write_reg(TEST0,    0x09)
        self._write_reg(MCSM0,    0x18)   # Calibrate when going to RX/TX
        self.set_freq_mhz(433.92)
        self.set_modulation(MOD_ASK)
        self.set_bandwidth(200)
        self.set_datarate(4800)
        self.idle()
