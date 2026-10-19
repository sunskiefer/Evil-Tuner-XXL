// Evil Tuner XXL -- KIWISDR: a public KiwiSDR receiver (kiwisdr.com) played into the ring, and the receiver list.
//
// The protocol is KiwiSDR's own, as its open-source clients speak it (github.com/jks-prv/kiwiclient): a WebSocket on
// http://host:port/kiwi/<n>/SND; text commands ("SET auth ...", "SET mod=am low_cut=-4900 high_cut=4900 freq=6070.000",
// "SET keepalive" once a second); binary messages back: "MSG k=v k=v ..." and "SND" + flags (1) + sequence (4, LE) +
// S-meter (2, BE: dBm = 0.1 * v - 127) + audio: IMA ADPCM (flag 0x10, low nibble first, the decoder's state carried
// from one block to the next) or big-endian s16, mono, at the receiver's rate (about 12 kHz). Checked against a live
// receiver: the decoded level matches the uncompressed stream's only with the state carried over.
//
// Manners: the receiver's slots are shared by everyone, so the session ends with the source (STOP, another source,
// another receiver) and is never re-opened after the receiver closed it (its time and inactivity limits stand); only a
// network drop is retried, three times. One status request per receiver on screen, at most every five minutes.
#include "et.h"
#include "curlx.h"
#include "param_defs.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <functional>

namespace et {

const char* kiwi_mode_word(int mode) {
  static const char* const kW[KIWI_NUM_MODES] = {"am", "usb", "lsb", "cw", "nbfm"};
  return kW[mode < 0 || mode >= KIWI_NUM_MODES ? 0 : mode];
}

static uint64_t now_ms() {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000u + (uint64_t)ts.tv_nsec / 1000000u;
}

// ------------------------------------------------------------------------------------------------ IMA ADPCM
struct Adpcm {
  int index = 0, prev = 0;
  void reset() { index = 0; prev = 0; }
  int16_t step(int code) {
    static const int16_t kStep[89] = {
        7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107,
        118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963,
        1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894,
        6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794,
        32767};
    static const int8_t kAdj[16] = {-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8};
    int s = kStep[index];
    index += kAdj[code];
    index = index < 0 ? 0 : (index > 88 ? 88 : index);
    int d = s >> 3;
    if (code & 1) d += s >> 2;
    if (code & 2) d += s >> 1;
    if (code & 4) d += s;
    if (code & 8) d = -d;
    prev += d;
    prev = prev < -32768 ? -32768 : (prev > 32767 ? 32767 : prev);
    return (int16_t)prev;
  }
  void decode(const uint8_t* p, size_t n, std::vector<float>& out) {
    for (size_t i = 0; i < n; ++i) {
      out.push_back(step(p[i] & 0x0F) * (1.f / 32768.f));
      out.push_back(step(p[i] >> 4) * (1.f / 32768.f));
    }
  }
};

// ------------------------------------------------------------------------------------------------ resampler
// Windowed-sinc interpolation (16 taps a side, Blackman window, a 256-step table) from the receiver's rate to 44.1 kHz;
// the cutoff sits just under the receiver's Nyquist, so the 12 kHz images are gone, not folded into the top octave.
struct Resampler {
  static const int kTaps = 16, kRes = 256;
  std::vector<float> table, hist;
  double pos = kTaps, ratio = 12000.0 / ET_SR;
  void init(double in_rate) {
    ratio = in_rate / ET_SR;
    double c = 0.9 * std::min(1.0, 1.0 / ratio);   // the cutoff, as a fraction of the input's Nyquist
    table.assign(kTaps * kRes * 2 + 2, 0.f);
    for (int i = 0; i <= kTaps * kRes * 2; ++i) {
      double x = (double)i / kRes - kTaps;
      double sinc = fabs(x) < 1e-9 ? 1.0 : sin(M_PI * c * x) / (M_PI * c * x);
      double w = 0.42 + 0.5 * cos(M_PI * x / kTaps) + 0.08 * cos(2.0 * M_PI * x / kTaps);
      table[i] = (float)(c * sinc * w);
    }
    hist.assign(kTaps, 0.f);
    pos = kTaps;
  }
  inline float h(double x) const {   // x in (-kTaps, kTaps)
    double t = (x + kTaps) * kRes;
    int i = (int)t;
    float f = (float)(t - i);
    return table[i] + f * (table[i + 1] - table[i]);
  }
  // input samples in, 44.1 kHz samples out
  void run(const std::vector<float>& in, std::vector<float>& out) {
    hist.insert(hist.end(), in.begin(), in.end());
    while ((int)pos + kTaps < (int)hist.size()) {
      int i0 = (int)pos;
      double fr = pos - i0;
      float acc = 0.f;
      for (int k = -kTaps + 1; k <= kTaps; ++k) acc += hist[i0 + k] * h(k - fr);
      out.push_back(acc);
      pos += ratio;
    }
    int drop = (int)pos - kTaps;   // keep kTaps samples of history before the next output
    if (drop > 0) {
      hist.erase(hist.begin(), hist.begin() + drop);
      pos -= drop;
    }
  }
};

// ------------------------------------------------------------------------------------------------ the WebSocket
struct Ws {
  int fd = -1;
  std::string rbuf;                // received, not yet parsed
  std::string frag;                // a fragmented message being put together
  int frag_op = 0;
  bool closed = false;             // the receiver closed it (a close frame, or the end of the stream)
  bool failed = false;             // a network error
  uint32_t rng = 0x9E3779B9u;
  ~Ws() { if (fd >= 0) close(fd); }
  uint32_t rnd() { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

  bool send_raw(const char* p, size_t n, int timeout_ms = 5000) {
    uint64_t t0 = now_ms();
    while (n) {
      ssize_t w = send(fd, p, n, MSG_NOSIGNAL);
      if (w > 0) { p += w; n -= (size_t)w; continue; }
      if (w < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) {
        if (now_ms() - t0 > (uint64_t)timeout_ms) { failed = true; return false; }
        struct pollfd pf = {fd, POLLOUT, 0};
        poll(&pf, 1, 100);
        continue;
      }
      failed = true;
      return false;
    }
    return true;
  }
  // one masked frame (a client must mask): text (1), pong (10), close (8)
  bool send_frame(int op, const std::string& payload) {
    std::string f;
    f.push_back((char)(0x80 | op));
    size_t n = payload.size();
    if (n < 126) f.push_back((char)(0x80 | n));
    else if (n < 65536) { f.push_back((char)(0x80 | 126)); f.push_back((char)(n >> 8)); f.push_back((char)n); }
    else { f.push_back((char)(0x80 | 127)); for (int i = 7; i >= 0; --i) f.push_back((char)((uint64_t)n >> (8 * i))); }
    uint32_t m = rnd();
    uint8_t mk[4] = {(uint8_t)(m >> 24), (uint8_t)(m >> 16), (uint8_t)(m >> 8), (uint8_t)m};
    f.append((const char*)mk, 4);
    for (size_t i = 0; i < n; ++i) f.push_back((char)(payload[i] ^ mk[i & 3]));
    return send_raw(f.data(), f.size());
  }
  bool text(const std::string& s) { return send_frame(1, s); }
  // reads what has arrived (waits up to timeout_ms for something); false on an error or the end of the stream
  bool fill(int timeout_ms) {
    struct pollfd pf = {fd, POLLIN, 0};
    int r = poll(&pf, 1, timeout_ms);
    if (r <= 0) return r == 0 || errno == EINTR;
    char b[16384];
    ssize_t n = recv(fd, b, sizeof b, 0);
    if (n > 0) { rbuf.append(b, (size_t)n); return true; }
    if (n == 0) { closed = true; return false; }
    if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) return true;
    failed = true;
    return false;
  }
  // the next whole message from rbuf: 1 text, 2 binary; 0 none yet. Control frames are answered here.
  int next(std::string& msg) {
    for (;;) {
      if (rbuf.size() < 2) return 0;
      const uint8_t* p = (const uint8_t*)rbuf.data();
      bool fin = p[0] & 0x80, masked = p[1] & 0x80;
      int op = p[0] & 0x0F;
      uint64_t n = p[1] & 0x7F;
      size_t h = 2;
      if (n == 126) { if (rbuf.size() < 4) return 0; n = ((uint64_t)p[2] << 8) | p[3]; h = 4; }
      else if (n == 127) {
        if (rbuf.size() < 10) return 0;
        n = 0;
        for (int i = 0; i < 8; ++i) n = (n << 8) | p[2 + i];
        h = 10;
      }
      if (n > (4u << 20)) { failed = true; return 0; }   // nothing a receiver sends is that big
      size_t mh = masked ? 4 : 0;
      if (rbuf.size() < h + mh + n) return 0;
      std::string pay = rbuf.substr(h + mh, (size_t)n);
      if (masked) for (size_t i = 0; i < pay.size(); ++i) pay[i] ^= p[h + (i & 3)];
      rbuf.erase(0, h + mh + (size_t)n);
      if (op == 8) { send_frame(8, pay.substr(0, 2)); closed = true; return 0; }
      if (op == 9) { send_frame(10, pay); continue; }
      if (op == 10) continue;
      if (op == 0) {   // continuation
        frag += pay;
        if (!fin) continue;
        msg.swap(frag);
        frag.clear();
        return frag_op == 1 ? 1 : 2;
      }
      if (!fin) { frag = pay; frag_op = op; continue; }
      msg.swap(pay);
      return op == 1 ? 1 : 2;
    }
  }
};

static std::string b64(const uint8_t* p, size_t n) {
  static const char* t = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  std::string o;
  for (size_t i = 0; i < n; i += 3) {
    uint32_t v = (uint32_t)p[i] << 16 | (i + 1 < n ? (uint32_t)p[i + 1] << 8 : 0) | (i + 2 < n ? p[i + 2] : 0);
    o.push_back(t[(v >> 18) & 63]);
    o.push_back(t[(v >> 12) & 63]);
    o.push_back(i + 1 < n ? t[(v >> 6) & 63] : '=');
    o.push_back(i + 2 < n ? t[v & 63] : '=');
  }
  return o;
}

// TCP to host:port; gives up when stop() says so (checked every 100 ms) or after timeout_ms
static int tcp_connect(const std::string& host, int port, int timeout_ms, const std::function<bool()>& stop,
                       std::string& err) {
  struct addrinfo hints;
  memset(&hints, 0, sizeof hints);
  hints.ai_family = AF_UNSPEC;
  hints.ai_socktype = SOCK_STREAM;
  struct addrinfo* res = nullptr;
  char ps[16];
  snprintf(ps, sizeof ps, "%d", port);
  int rc = getaddrinfo(host.c_str(), ps, &hints, &res);
  if (rc != 0 || !res) { err = "CAN'T FIND THE RECEIVER (NO INTERNET?)"; return -1; }
  int fd = -1;
  err = "THE RECEIVER DOESN'T ANSWER";
  for (struct addrinfo* a = res; a && fd < 0 && !stop(); a = a->ai_next) {
    int s = socket(a->ai_family, a->ai_socktype | SOCK_CLOEXEC, a->ai_protocol);
    if (s < 0) continue;
    fcntl(s, F_SETFL, fcntl(s, F_GETFL) | O_NONBLOCK);
    int r = connect(s, a->ai_addr, a->ai_addrlen);
    if (r != 0 && errno != EINPROGRESS) { close(s); continue; }
    uint64_t t0 = now_ms();
    bool ok = r == 0;
    while (!ok && !stop() && now_ms() - t0 < (uint64_t)timeout_ms) {
      struct pollfd pf = {s, POLLOUT, 0};
      if (poll(&pf, 1, 100) > 0) {
        int e = 0;
        socklen_t el = sizeof e;
        getsockopt(s, SOL_SOCKET, SO_ERROR, &e, &el);
        if (e == 0) ok = true;
        else { if (e == ECONNREFUSED) err = "THE RECEIVER REFUSED THE CONNECTION"; break; }
      }
    }
    if (ok) {
      int one = 1;
      setsockopt(s, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
      fd = s;
    } else close(s);
  }
  freeaddrinfo(res);
  return fd;
}

static std::string url_unescape(const std::string& s) {
  std::string o;
  for (size_t i = 0; i < s.size(); ++i) {
    if (s[i] == '%' && i + 2 < s.size()) {
      o.push_back((char)strtol(s.substr(i + 1, 2).c_str(), nullptr, 16));
      i += 2;
    } else o.push_back(s[i]);
  }
  return o;
}

// "http://host:port/path" (or without the scheme) -> rx; false if it isn't a plain-http address
// The port: as written; without one, 80 when a scheme was written (a browser's address), else KiwiSDR's 8073.
static bool parse_url(std::string u, KiwiRx& rx) {
  if (u.compare(0, 8, "https://") == 0 || u.compare(0, 6, "wss://") == 0) return false;
  bool scheme = false;
  if (u.compare(0, 7, "http://") == 0) { u = u.substr(7); scheme = true; }
  else if (u.compare(0, 5, "ws://") == 0) { u = u.substr(5); scheme = true; }
  size_t sl = u.find('/');
  std::string hp = u.substr(0, sl);
  std::string path = sl == std::string::npos ? "" : u.substr(sl);
  while (!path.empty() && path.back() == '/') path.pop_back();
  if (path.compare(0, 6, "/kiwi/") == 0 || path == "/kiwi") path.clear();
  size_t co = hp.rfind(':');
  int port = scheme ? 80 : 8073;
  if (co != std::string::npos) {
    port = atoi(hp.c_str() + co + 1);
    hp = hp.substr(0, co);
  }
  if (hp.empty() || port <= 0 || port > 65535) return false;
  rx.host = hp;
  rx.port = port;
  rx.path = path;
  return true;
}

// the opening handshake; 101 = a WebSocket. A redirect fills `location`.
static int ws_handshake(Ws& ws, const KiwiRx& rx, std::string& location, const std::function<bool()>& stop) {
  uint8_t key[16];
  for (auto& k : key) k = (uint8_t)ws.rnd();
  char res[64];
  snprintf(res, sizeof res, "/kiwi/%u/SND", (unsigned)(now_ms() % 1000000000u));
  std::string req = "GET " + rx.path + res + " HTTP/1.1\r\nHost: " + rx.host +
                    (rx.port == 80 ? "" : ":" + std::to_string(rx.port)) +
                    "\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: " + b64(key, 16) +
                    "\r\nSec-WebSocket-Version: 13\r\nUser-Agent: EvilTunerXXL/" ET_VERSION " (MPC OS plugin)\r\n\r\n";
  if (!ws.send_raw(req.data(), req.size())) return -1;
  uint64_t t0 = now_ms();
  size_t end;
  while ((end = ws.rbuf.find("\r\n\r\n")) == std::string::npos) {
    if (stop() || now_ms() - t0 > 10000 || ws.rbuf.size() > 16384) return -1;
    if (!ws.fill(100)) return -1;
  }
  std::string head = ws.rbuf.substr(0, end + 2);
  ws.rbuf.erase(0, end + 4);
  int code = 0;
  if (sscanf(head.c_str(), "HTTP/%*s %d", &code) != 1) return -1;
  if (code >= 300 && code < 400) {
    std::string low = head;
    for (auto& c : low) c = (char)tolower((unsigned char)c);
    size_t l = low.find("\r\nlocation:");
    if (l != std::string::npos) {
      size_t a = l + 11, e = head.find("\r\n", a);
      location = head.substr(a, e - a);
      while (!location.empty() && location[0] == ' ') location.erase(0, 1);
    }
  }
  return code;
}

// ------------------------------------------------------------------------------------------------ Sources::run_kiwi
void Sources::run_kiwi(const KiwiRx& rx0, uint32_t g) {
  KiwiRx rx = rx0;
  auto stop = [&] { return quit_.load() || gen_.load() != g; };
  std::string label = rx.name.empty() ? rx.host : rx.name;
  set_title(label);
  kiwi_rssi = -200.f;
  int drops = 0, redirects = 0;
  while (!stop()) {
    state = 1;
    set_status(drops ? "RECONNECTING" : "CONNECTING");
    std::string err;
    Ws ws;
    ws.rng ^= (uint32_t)now_ms() * 2654435761u;
    ws.fd = tcp_connect(rx.host, rx.port, 8000, stop, err);
    if (stop()) return;
    if (ws.fd < 0) {
      log_line("kiwi %s: %s", rx.id().c_str(), err.c_str());
      if (drops && drops <= 3) { drops++; for (int i = 0; i < 30 && !stop(); ++i) usleep(100000); continue; }
      state = 4;
      set_status(err);
      return;
    }
    std::string location;
    int code = ws_handshake(ws, rx, location, stop);
    if (stop()) return;
    if (code >= 300 && code < 400 && !location.empty() && redirects < 3) {
      KiwiRx to = rx;
      size_t k = location.find("/kiwi/");   // keep only host, port and the folder in front of /kiwi/
      if (k != std::string::npos) location = location.substr(0, k);
      if (parse_url(location, to)) { log_line("kiwi redirect -> %s", to.id().c_str()); rx = to; redirects++; continue; }
    }
    if (code != 101) {
      log_line("kiwi %s: handshake %d", rx.id().c_str(), code);
      state = 4;
      set_status(code == 404 ? "THE RECEIVER IS OFFLINE" : (code > 0 ? "NOT A KIWISDR (HTTP " + std::to_string(code) + ")" : "NO ANSWER FROM THE RECEIVER"));
      return;
    }
    state = 2;
    set_status("WAITING FOR THE RECEIVER");
    ws.text("SET auth t=kiwi p=#");
    Adpcm adpcm;
    Resampler rs;
    bool started = false, compressed_last = false, audio = false;
    double foff = 0;
    uint32_t tune_rev = 0xFFFFFFFFu;
    KiwiTune tune;
    uint64_t last_rx = now_ms(), last_keep = 0;
    std::string why;                               // set when the receiver turns us away
    std::vector<float> pcm, out, lr;
    auto send_tune = [&] {
      double f = tune.khz - foff;
      if (f < 0) f = 0;
      char b[128];
      snprintf(b, sizeof b, "SET mod=%s low_cut=%d high_cut=%d freq=%.3f", kiwi_mode_word(tune.mode), tune.lo, tune.hi, f);
      ws.text(b);
    };
    while (!stop() && !ws.closed && !ws.failed && why.empty()) {
      if (!ws.fill(50)) break;
      uint64_t t = now_ms();
      std::string m;
      int op;
      while (why.empty() && (op = ws.next(m)) != 0) {
        last_rx = t;
        if (m.size() < 3) continue;
        if (m.compare(0, 3, "MSG") == 0) {
          std::string body = m.size() > 4 ? m.substr(4) : "";
          size_t a = 0;
          while (a < body.size()) {
            size_t e = body.find(' ', a);
            std::string pair = body.substr(a, e == std::string::npos ? std::string::npos : e - a);
            a = e == std::string::npos ? body.size() : e + 1;
            size_t eq = pair.find('=');
            std::string k = pair.substr(0, eq), v = eq == std::string::npos ? "" : pair.substr(eq + 1);
            if (k == "too_busy") why = "RECEIVER FULL: ALL " + v + " CHANNELS IN USE";
            else if (k == "badp" && v != "0") {
              why = v == "5" ? "ONE CONNECTION PER ADDRESS: THIS RECEIVER IS ALREADY IN USE FROM HERE"
                             : (v == "1" ? "RECEIVER FULL, OR IT NEEDS A PASSWORD" : "THE RECEIVER REFUSED (" + v + ")");
            } else if (k == "down") why = "THE RECEIVER IS DOWN FOR NOW";
            else if (k == "redirect" && redirects < 3) {
              KiwiRx to = rx;
              if (parse_url(url_unescape(v), to)) { rx = to; redirects++; why = "\x01"; }   // reconnect there
            } else if (k == "audio_rate") {
              ws.text("SET AR OK in=" + v + " out=44100");
            } else if (k == "freq_offset") {
              foff = atof(v.c_str());
            } else if (k == "sample_rate") {
              double sr = atof(v.c_str());
              rs.init(sr > 4000 && sr < 50000 ? sr : 12000.0);
              ws.text("SET squelch=0 max=0");
              ws.text("SET genattn=0");
              ws.text("SET gen=0 mix=-1");
              ws.text("SET ident_user=EvilTunerXXL");
              kiwi_tune_read(tune, tune_rev);
              send_tune();
              ws.text("SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50");
              ws.text("SET compression=1");
              ws.text("SET keepalive");
              last_keep = t;
              started = true;
              log_line("kiwi %s: rate %.3f", rx.id().c_str(), sr);
            }
          }
        } else if (m.compare(0, 3, "SND") == 0 && m.size() >= 10 && started) {
          const uint8_t* p = (const uint8_t*)m.data();
          int flags = p[3];
          int sm = (p[8] << 8) | p[9];
          kiwi_rssi = 0.1f * sm - 127.f;
          pcm.clear();
          if (flags & 0x10) {
            if (!compressed_last) adpcm.reset();
            adpcm.decode(p + 10, m.size() - 10, pcm);
          } else {
            for (size_t i = 10; i + 1 < m.size(); i += 2) pcm.push_back((int16_t)((p[i] << 8) | p[i + 1]) * (1.f / 32768.f));
          }
          compressed_last = flags & 0x10;
          out.clear();
          rs.run(pcm, out);
          lr.resize(out.size() * 2);
          for (size_t i = 0; i < out.size(); ++i) lr[2 * i] = lr[2 * i + 1] = out[i];
          size_t done = 0;
          while (done < out.size() && !stop()) {
            done += ring.write(lr.data() + done * 2, (uint32_t)(out.size() - done));
            if (done < out.size()) usleep(5000);
          }
          if (!audio) { audio = true; drops = 0; state = 3; set_status("PLAYING"); }
        }
      }
      if (!why.empty()) break;
      if (started) {
        if (kiwi_tune_read(tune, tune_rev)) send_tune();
        if (t - last_keep >= 1000) { ws.text("SET keepalive"); last_keep = t; }
      }
      if (t - last_rx > 12000) { ws.failed = true; log_line("kiwi %s: nothing for 12 s", rx.id().c_str()); }
    }
    if (stop()) { ws.send_frame(8, std::string("\x03\xe8", 2)); return; }   // a polite close: the slot frees at once
    if (why == "\x01") { log_line("kiwi redirect -> %s", rx.id().c_str()); continue; }
    if (!why.empty()) {
      log_line("kiwi %s: %s", rx.id().c_str(), why.c_str());
      state = 4;
      set_status(why);
      return;
    }
    if (ws.closed) {   // the receiver ended the session (its time limit, its inactivity limit, a restart): not re-opened
      log_line("kiwi %s: closed by the receiver", rx.id().c_str());
      state = 4;
      set_status(audio ? "THE RECEIVER ENDED THE SESSION (ITS TIME LIMIT?)" : "THE RECEIVER CLOSED THE CONNECTION");
      return;
    }
    // a network drop: up to three tries
    if (++drops > 3) {
      state = 4;
      set_status("NETWORK LOST");
      return;
    }
    for (int i = 0; i < 30 && !stop(); ++i) usleep(100000);
  }
}

// ------------------------------------------------------------------------------------------------ the receiver list
// Public receivers (receiverbook.de / kiwisdr.com listings, 2026-10): plain http only. Their owners may move or retire
// them; the status shows which answer. A user's own list (kiwisdr.txt in the plugin's data folder) comes first.
std::vector<KiwiRx> KiwiDir::builtin() {
  static const struct { const char *host; int port; const char *name, *loc; } kRx[] = {
      {"pallas-kiwi.ddns.net", 8073, "PALLAS, LAPLAND", "FI"},
      {"oh1rj.proxy.kiwisdr.com", 8073, "PARAINEN", "FI"},
      {"oh1ct.sytes.net", 8073, "LOPPI (OH1CT)", "FI"},
      {"21612.proxy.kiwisdr.com", 8073, "ASIKKALA", "FI"},
      {"kiwi-kuo.aprs.fi", 8073, "KUOPIO", "FI"},
      {"sm2byc.ddns.net", 8073, "SM2BYC", "SE"},
      {"la2g.ddns.net", 8072, "LA2G", "NO"},
      {"86.52.211.220", 8073, "SOENDERBORG", "DK"},
      {"okno.ddns.net", 8073, "SILESIA", "PL"},
      {"sdr.ok2kyj.cz", 8073, "OLOMOUC", "CZ"},
      {"db0ovp.de", 8073, "GREIFSWALD", "DE"},
      {"dh9zig-p.proxy.kiwisdr.com", 8073, "SENZIG", "DE"},
      {"kiwisdr.servepics.com", 8073, "GERWISCH", "DE"},
      {"dl1bajkiwisdr.ddns.net", 8074, "HOOKSIEL", "DE"},
      {"da1vid.ipv64.net", 8073, "DORTMUND", "DE"},
      {"178.63.122.223", 8073, "BAUNATAL", "DE"},
      {"df4or.ddns.net", 8073, "HERXHEIM", "DE"},
      {"dg2sax.ddns.net", 8074, "ALBSTADT", "DE"},
      {"21033.proxy.kiwisdr.com", 8073, "BEILEN (PA3GUK)", "NL"},
      {"pb8w.proxy.kiwisdr.com", 8073, "ASSEN (PB8W)", "NL"},
      {"oe1xtu.proxy.kiwisdr.com", 8073, "OE1XTU", "AT"},
      {"oe3akb.ddns.net", 8073, "OBERWOELBLING", "AT"},
      {"hb9re.ddns.net", 8081, "BODENBERG", "CH"},
      {"80.75.112.98", 8073, "OBERE WARTE ZH", "CH"},
      {"21699.proxy.kiwisdr.com", 8073, "MUGGIA, TRIESTE", "IT"},
      {"sdr.autreradioautreculture.com", 8073, "TREMOLAT", "FR"},
      {"f5nkp.freeboxos.fr", 8073, "NEAR PARIS (F5NKP)", "FR"},
      {"chantilly-sdr.ddns.net", 8073, "CHANTILLY", "FR"},
      {"wessex.zapto.org", 8073, "WESSEX (G8JNJ)", "GB"},
      {"sdr.gb0snb.com", 8073, "BRENTWOOD BUNKER", "GB"},
      {"msars.ddns.net", 8073, "BURGESS HILL", "GB"},
      {"remoteradio.myddns.me", 8086, "BEDFORD", "GB"},
      {"kiwi.minish.org", 8073, "CASTLEBAR", "IE"},
      {"emeraldsdr.ddns.net", 8073, "CARLOW", "IE"},
      {"sdr.k1vl.com", 8073, "SHREWSBURY, VERMONT", "US"},
      {"hill.n8ga.org", 8073, "CABLE, OHIO", "US"},
      {"n0ls.homedns.org", 8073, "DENVER", "US"},
      {"sdr.ddns.net", 8073, "CROWLEY, TEXAS", "US"},
  };
  std::vector<KiwiRx> v;
  for (auto& k : kRx) {
    KiwiRx r;
    r.host = k.host;
    r.port = k.port;
    r.name = k.name;
    r.loc = k.loc;
    v.push_back(r);
  }
  return v;
}

bool KiwiDir::parse_line(const std::string& line0, KiwiRx& rx) {
  std::string line = line0;
  size_t h = line.find('#');
  if (h != std::string::npos) line = line.substr(0, h);
  while (!line.empty() && isspace((unsigned char)line.back())) line.pop_back();
  size_t a = 0;
  while (a < line.size() && isspace((unsigned char)line[a])) a++;
  if (a >= line.size()) return false;
  size_t e = a;
  while (e < line.size() && !isspace((unsigned char)line[e])) e++;
  KiwiRx r;
  if (!parse_url(line.substr(a, e - a), r)) return false;
  while (e < line.size() && isspace((unsigned char)line[e])) e++;
  r.name = line.substr(e);
  if (r.name.empty()) r.name = r.host;
  for (auto& c : r.name) c = (char)toupper((unsigned char)c);
  r.user = true;
  rx = r;
  return true;
}

void KiwiDir::parse_status(const std::string& body, KiwiRx& rx) {
  size_t a = 0;
  bool off = false;
  while (a < body.size()) {
    size_t e = body.find('\n', a);
    std::string l = body.substr(a, e == std::string::npos ? std::string::npos : e - a);
    a = e == std::string::npos ? body.size() : e + 1;
    if (!l.empty() && l.back() == '\r') l.pop_back();
    size_t eq = l.find('=');
    if (eq == std::string::npos) continue;
    std::string k = l.substr(0, eq), v = l.substr(eq + 1);
    if (k == "users") rx.users = atoi(v.c_str());
    else if (k == "users_max") rx.users_max = atoi(v.c_str());
    else if (k == "offline") off = off || v == "yes";
    else if (k == "status") off = off || (v != "active" && v != "private");
  }
  rx.offline = off;
}

static const char* kTemplate =
    "# Your own KiwiSDR receivers for Evil Tuner XXL (KIWISDR), listed before the built-in ones.\n"
    "# One per line: the address as your browser shows it, then a name. Plain http only. Examples:\n"
    "#   http://pallas-kiwi.ddns.net:8073 PALLAS, LAPLAND\n"
    "#   my-kiwi.example.org:8073 MY RECEIVER\n"
    "# Find receivers at kiwisdr.com/public or receiverbook.de. Reopen the plugin after editing.\n";

void KiwiDir::start(const std::string& data_dir) {
  list.clear();
  if (!data_dir.empty()) {
    std::string path = data_dir + "/kiwisdr.txt";
    FILE* f = fopen(path.c_str(), "r");
    if (f) {
      char line[512];
      while (fgets(line, sizeof line, f)) {
        KiwiRx r;
        if (parse_line(line, r)) list.push_back(r);
      }
      fclose(f);
    } else if ((f = fopen(path.c_str(), "w"))) {
      fputs(kTemplate, f);
      fclose(f);
    }
  }
  for (auto& r : builtin())
    if (std::none_of(list.begin(), list.end(), [&](const KiwiRx& u) { return u.id() == r.id(); })) list.push_back(r);
  quit_ = false;
  th_ = std::thread([this] { worker(); });
}

void KiwiDir::stop() {
  quit_ = true;
  cv_.notify_all();
  if (th_.joinable()) th_.join();
}

bool KiwiDir::probe(const std::vector<std::string>& ids) {
  std::unique_lock<std::mutex> lk(mu_, std::try_to_lock);   // the audio thread asks: never waits (asks again later)
  if (!lk.owns_lock()) return false;
  want_.clear();
  for (auto& id : ids)
    for (auto& r : list)
      if (r.id() == id) want_.push_back(r);
  cv_.notify_all();
  return true;
}

bool KiwiDir::take(std::vector<KiwiRx>& status) {
  std::unique_lock<std::mutex> lk(mu_, std::try_to_lock);
  if (!lk.owns_lock() || got_.empty()) return false;
  status.swap(got_);
  got_.clear();
  return true;
}

static size_t on_status(char* p, size_t sz, size_t n, void* ud) {
  std::string* s = static_cast<std::string*>(ud);
  if (s->size() < 16384) s->append(p, sz * n);
  return sz * n;
}

void KiwiDir::worker() {
  for (;;) {
    KiwiRx r;
    {
      std::unique_lock<std::mutex> lk(mu_);
      cv_.wait(lk, [&] { return quit_.load() || !want_.empty(); });
      if (quit_.load()) return;
      r = want_.front();
      want_.erase(want_.begin());
      uint64_t t = now_ms();
      bool recent = false;
      for (auto& a : asked_) if (a.first == r.id() && t - a.second < 300000) recent = true;
      if (recent) continue;
      asked_.erase(std::remove_if(asked_.begin(), asked_.end(), [&](const std::pair<std::string, uint64_t>& a) { return a.first == r.id(); }), asked_.end());
      asked_.push_back({r.id(), t});
    }
    CurlApi& cu = curl();
    if (!cu.ok) continue;
    std::string body;
    CURL* c = cu.easy_init();
    if (!c) continue;
    std::string url = "http://" + r.host + ":" + std::to_string(r.port) + r.path + "/status";
    curl_common(c, 4);
    cu.easy_setopt(c, CURLOPT_URL, url.c_str());
    cu.easy_setopt(c, CURLOPT_TIMEOUT, 6L);
    cu.easy_setopt(c, CURLOPT_WRITEFUNCTION, on_status);
    cu.easy_setopt(c, CURLOPT_WRITEDATA, &body);
    CURLcode rc = cu.easy_perform(c);
    long code = 0;
    cu.easy_getinfo(c, CURLINFO_RESPONSE_CODE, &code);
    cu.easy_cleanup(c);
    if (rc == CURLE_OK && code == 200 && body.find("users_max=") != std::string::npos) parse_status(body, r);
    else r.offline = true;
    std::lock_guard<std::mutex> lk(mu_);
    got_.push_back(r);
  }
}

}  // namespace et
