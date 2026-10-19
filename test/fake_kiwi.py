#!/usr/bin/env python3
"""A stand-in KiwiSDR for the offline tests: speaks the receiver's side of the protocol (WebSocket on /kiwi/<n>/SND,
MSG lines, SND blocks) and plays a sine whose pitch follows the tuned frequency: 1000 Hz + 100 Hz per kHz above
6070 kHz (so a retune is audible in the recording). The first 12 blocks are IMA ADPCM (the decoder's state carried
over, as a real receiver does), the rest big-endian s16, to test both. Every command received is logged.

    fake_kiwi.py <port> <log file> [--busy] [--close-after S] [--stall-after S]
--close-after: the receiver ends the session (a close frame), as its time limit would; --stall-after: it goes silent
with the connection open, as a dropped network would (the first connection only)."""
import base64
import hashlib
import math
import socket
import struct
import sys
import threading
import time

RATE = 12001.0
STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97,
        107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
        876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428,
        4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350,
        22385, 24623, 27086, 29794, 32767]
ADJ = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8]


class Enc:
    def __init__(self):
        self.index, self.prev = 0, 0

    def code(self, x):
        step = STEP[self.index]
        diff = x - self.prev
        c = 0
        if diff < 0:
            c, diff = 8, -diff
        if diff >= step: c |= 4; diff -= step
        if diff >= step >> 1: c |= 2; diff -= step >> 1
        if diff >= step >> 2: c |= 1
        # decode exactly as the receiver's client does, to track its state
        d = step >> 3
        if c & 1: d += step >> 2
        if c & 2: d += step >> 1
        if c & 4: d += step
        if c & 8: d = -d
        self.prev = max(-32768, min(32767, self.prev + d))
        self.index = max(0, min(88, self.index + ADJ[c]))
        return c

    def block(self, samples):
        out = bytearray()
        for i in range(0, len(samples), 2):
            lo = self.code(samples[i])
            hi = self.code(samples[i + 1])
            out.append(lo | (hi << 4))
        return bytes(out)


def frame(op, payload):
    n = len(payload)
    h = bytes([0x80 | op])
    if n < 126: h += bytes([n])
    elif n < 65536: h += bytes([126]) + struct.pack(">H", n)
    else: h += bytes([127]) + struct.pack(">Q", n)
    return h + payload


def read_frames(sock, buf):
    """complete client frames from buf (masked): [(op, payload)], rest"""
    out = []
    while len(buf) >= 2:
        op, n, h = buf[0] & 15, buf[1] & 127, 2
        if n == 126:
            if len(buf) < 4: break
            n, h = struct.unpack(">H", buf[2:4])[0], 4
        elif n == 127:
            if len(buf) < 10: break
            n, h = struct.unpack(">Q", buf[2:10])[0], 10
        masked = buf[1] & 128
        mk = buf[h:h + 4] if masked else b"\0\0\0\0"
        h += 4 if masked else 0
        if len(buf) < h + n: break
        pay = bytes(b ^ mk[i & 3] for i, b in enumerate(buf[h:h + n]))
        out.append((op, pay, bool(masked)))
        buf = buf[h + n:]
    return out, buf


OPTS = {"close": None, "stall": None, "conns": 0}


def serve(conn, log, busy):
    OPTS["conns"] += 1
    first = OPTS["conns"] == 1
    req = b""
    while b"\r\n\r\n" not in req:
        d = conn.recv(4096)
        if not d: return
        req += d
    head, rest = req.split(b"\r\n\r\n", 1)
    lines = head.decode().split("\r\n")
    log.write("REQ %s\n" % lines[0])
    key = [l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("sec-websocket-key:")][0]
    acc = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
    conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  "Sec-WebSocket-Accept: %s\r\n\r\n" % acc).encode())
    msg = lambda t: conn.sendall(frame(2, b"MSG " + t.encode()))
    state = {"freq": None, "comp": True, "keep": 0, "mod": None}
    buf = rest
    conn.settimeout(0.02)
    enc = Enc()
    seq, phase, t0, sent = 0, 0.0, None, 0
    authed = False
    while True:
        try:
            d = conn.recv(65536)
            if not d:
                log.write("EOF\n"); return
            buf += d
        except socket.timeout:
            pass
        except OSError:
            return
        fr, buf = read_frames(conn, buf)
        for op, pay, masked in fr:
            if op == 8:
                log.write("CLOSE masked=%d\n" % masked); log.flush(); return
            if op != 1: continue
            t = pay.decode()
            log.write("CMD masked=%d %s\n" % (masked, t)); log.flush()
            if t.startswith("SET auth") and not authed:
                authed = True
                if busy:
                    msg("too_busy=4"); continue
                msg("sample_rate=%.6f" % RATE)
                msg("client_public_ip=127.0.0.1")
                msg("badp=0")
                msg("version_maj=1 version_min=902 freq_offset=0.000")
                msg("center_freq=15000000 bandwidth=30000000 adc_clk_nom=66666600")
                msg("audio_init=0 audio_rate=12000")
            elif t.startswith("SET mod="):
                kv = dict(p.split("=", 1) for p in t[4:].split() if "=" in p)
                state["freq"] = float(kv["freq"]); state["mod"] = kv["mod"]
            elif t.startswith("SET keepalive"):
                state["keep"] += 1
        if state["freq"] is None: continue
        if t0 is None: t0 = time.time()
        if OPTS["close"] is not None and time.time() - t0 > OPTS["close"]:
            log.write("SERVER CLOSE\n")
            conn.sendall(frame(8, struct.pack(">H", 1000)))
            time.sleep(0.5)
            conn.close()
            return
        if first and OPTS["stall"] is not None and time.time() - t0 > OPTS["stall"]:
            continue
        # real time: 2048 samples a block (compressed), 512 uncompressed
        n = 2048 if seq < 12 else 512
        due = (time.time() - t0) * RATE
        while sent + n <= due + n:
            f = 1000.0 + 100.0 * (state["freq"] - 6070.0)
            s = []
            for i in range(n):
                s.append(int(12000 * math.sin(phase)))
                phase += 2 * math.pi * f / RATE
            phase %= 2 * math.pi
            seq += 1
            flags = 0x10 if seq <= 12 else 0
            data = enc.block(s) if flags else b"".join(struct.pack(">h", x) for x in s)
            sm = int((-80 + 127) * 10)
            try:
                conn.sendall(frame(2, b"SND" + bytes([flags]) + struct.pack("<I", seq) + struct.pack(">H", sm) + data))
            except OSError:
                return
            sent += n
            n = 2048 if seq < 12 else 512


def main():
    port, logname = int(sys.argv[1]), sys.argv[2]
    busy = "--busy" in sys.argv
    for k, flag in (("close", "--close-after"), ("stall", "--stall-after")):
        if flag in sys.argv:
            OPTS[k] = float(sys.argv[sys.argv.index(flag) + 1])
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(4)
    log = open(logname, "w", buffering=1)
    while True:
        c, _ = srv.accept()
        threading.Thread(target=serve, args=(c, log, busy), daemon=True).start()


if __name__ == "__main__":
    main()
