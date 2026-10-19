// Evil Tuner XXL -- shared definitions.
//
// The instrument plays a SOURCE (internet radio, a phone over Roc, an iPhone over AirPlay) through a chain modelled on
// the Endorphin.es Evil Pet's idea (granular voice, filter, saturator, reverb; the concept only, none of its code):
//   source ring -> tape (rolling) -> looper -> grains (+ keys, osc) -> filter -> character -> saturator -> gate/stutter
//   -> Erica delay -> reverb -> limiter -> volume
// Threads: MPC's audio thread runs render() and the parameter calls (one at a time: the wrapper's lock). The sources
// (source.cc) and the station directory (net.cc) run on their own threads and talk to the audio thread through
// lock-free rings and small mailboxes the audio thread polls with try_lock (it never waits).
#pragma once
#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#define ET_SR 44100
#define ET_VERSION "0.2.0"

namespace et {

inline float clampf(float v, float a, float b) { return v < a ? a : (v > b ? b : v); }

// a line in /tmp/eviltuner.log (source.cc)
void log_line(const char* fmt, ...) __attribute__((format(printf, 1, 2)));

// ------------------------------------------------------------------------------------------------ single-producer ring
// Interleaved stereo float frames. The source's reader thread writes, the audio thread reads.
struct Ring {
  std::vector<float> buf;
  uint32_t mask = 0;
  std::atomic<uint32_t> w{0}, r{0};
  void init(uint32_t frames_pow2) { buf.assign(frames_pow2 * 2, 0.f); mask = frames_pow2 - 1; w = 0; r = 0; }
  uint32_t fill() const { return w.load(std::memory_order_acquire) - r.load(std::memory_order_acquire); }
  uint32_t space() const { return mask + 1 - fill(); }
  void clear() { r.store(w.load()); }
  // producer
  uint32_t write(const float* lr, uint32_t frames) {
    uint32_t sp = space();
    if (frames > sp) frames = sp;
    uint32_t wi = w.load(std::memory_order_relaxed);
    for (uint32_t i = 0; i < frames; ++i) {
      uint32_t k = ((wi + i) & mask) * 2;
      buf[k] = lr[2 * i];
      buf[k + 1] = lr[2 * i + 1];
    }
    w.store(wi + frames, std::memory_order_release);
    return frames;
  }
  // consumer
  void peek(uint32_t off, float& l, float& r_) const {
    uint32_t k = ((r.load(std::memory_order_relaxed) + off) & mask) * 2;
    l = buf[k];
    r_ = buf[k + 1];
  }
  void advance(uint32_t n) { r.store(r.load(std::memory_order_relaxed) + n, std::memory_order_release); }
};

// ------------------------------------------------------------------------------------------------ stations
struct Station {
  std::string uuid, name, url, codec, country, tags;
  int bitrate = 0;
  bool hls = false;
};

enum SourceKind { SRC_NONE = 0, SRC_RADIO, SRC_PHONE, SRC_AIRPLAY, SRC_KIWI };

// ------------------------------------------------------------------------------------------------ KiwiSDR (kiwi.cc)
// A public KiwiSDR receiver: http://host:port/path (the path is empty unless it sits behind a web server's sub-folder)
struct KiwiRx {
  std::string host, path, name, loc;
  int port = 8073;
  bool user = false;               // from the user's own kiwisdr.txt
  // its /status, when probed (kiwi.cc KiwiDir)
  int users = -1, users_max = -1;  // -1: not known yet
  bool offline = false;
  std::string id() const { return host + ":" + std::to_string(port) + path; }
};

// What the receiver is told to play: the frequency (kHz), the mode and the passband (Hz, around the carrier)
struct KiwiTune {
  double khz = 6070.0;
  int mode = 0;                    // KM_AM .. KM_NFM (param_defs.h)
  int lo = -4900, hi = 4900;
};
const char* kiwi_mode_word(int mode);   // the Kiwi protocol's name for a mode ("am", "usb", ...)

// The receiver list (the user's own kiwisdr.txt first, then the built-in one) and a worker that asks the shown
// receivers for their /status (users, offline), at most every few minutes each.
class KiwiDir {
 public:
  void start(const std::string& data_dir);
  void stop();
  std::vector<KiwiRx> list;                        // the audio / UI thread's copy (loaded once, at start)
  bool probe(const std::vector<std::string>& ids);  // the receivers on screen: ask their status (newest request wins;
                                                    // false: busy, ask again)
  bool take(std::vector<KiwiRx>& status);           // try_lock: probed receivers since the last take
  static std::vector<KiwiRx> builtin();
  static bool parse_line(const std::string& line, KiwiRx& rx);   // "host[:port][/path] [name...]"
  static void parse_status(const std::string& body, KiwiRx& rx);
 private:
  void worker();
  std::thread th_;
  std::mutex mu_;
  std::condition_variable cv_;
  std::vector<KiwiRx> want_, got_;
  std::vector<std::pair<std::string, uint64_t>> asked_;   // id, when (ms): not again for a while
  std::atomic<bool> quit_{false};
};

// ------------------------------------------------------------------------------------------------ the sources (source.cc)
class Sources {
 public:
  void start(const std::string& plugin_dir, const std::string& data_dir);
  void stop_all();                                 // instance closing: ends every thread and child
  // requests (audio or UI thread; never block)
  void play_radio(const Station& s);
  void play_phone();
  void play_airplay();
  void play_kiwi(const KiwiRx& rx, const KiwiTune& t);
  void kiwi_tune(const KiwiTune& t);               // retune while connected (lock-free: any thread)
  void stop();                                     // silence, children ended
  // the audio thread's view
  Ring ring;
  std::atomic<int> kind{SRC_NONE};
  std::atomic<int> state{0};                       // 0 idle, 1 connecting, 2 buffering, 3 playing, 4 error
  std::atomic<uint32_t> title_rev{0};
  std::atomic<float> kiwi_rssi{-200.f};            // dBm of the last audio block (-200: none yet)
  bool title(std::string& out);                    // try_lock: the "now playing" text, when it changed
  bool status(std::string& out);                   // try_lock: a short status / error line
  std::string ip_text();                           // this device's address(es), for the PHONE / AIRPLAY pages
  std::string helper_dir;
 private:
  void worker();
  void run_radio(const Station& s, uint32_t gen);
  void run_child(int kind, uint32_t gen);
  void run_kiwi(const KiwiRx& rx, uint32_t gen);   // kiwi.cc
  bool kiwi_tune_read(KiwiTune& t, uint32_t& rev);
  void set_title(const std::string& t);
  void set_status(const std::string& t);
  std::thread th_;
  std::mutex mu_;                                  // guards the request and the texts below
  std::condition_variable cv_;
  int want_kind_ = SRC_NONE;
  Station want_station_;
  KiwiRx want_rx_;
  // the tuning mailbox (a seqlock: odd while being written)
  std::atomic<uint32_t> tune_seq_{0};
  std::atomic<int64_t> tune_hz_{6070000};
  std::atomic<int> tune_mode_{0}, tune_lo_{-4900}, tune_hi_{4900};
  std::atomic<uint32_t> gen_{0};
  std::atomic<bool> quit_{false};
  std::string title_, status_, data_dir_;
  bool title_new_ = false, status_new_ = false;
  friend struct SourceInternals;
};

// ------------------------------------------------------------------------------------------------ the directory (net.cc)
struct Query {
  int kind = 0;                                    // 0 browse (filters), 1 text search
  std::string text, tag, countrycode, order;
  bool reverse = true;
  int bitrate_max = 0;                             // 0: any
  int offset = 0;
};

class Directory {
 public:
  void start(const std::string& data_dir);
  void stop();
  void request(const Query& q);                    // newest request wins
  void click(const std::string& uuid);             // tells Radio Browser a station was played (its guidelines)
  // results: polled by the audio thread with try_lock
  bool take(std::vector<Station>& out, std::string& msg, int& offset, bool& more);
  std::atomic<int> busy{0};
  // favourites (the audio / UI thread; the file is written on the worker)
  std::vector<Station> favs;
  bool is_fav(const std::string& uuid) const;
  void toggle_fav(const Station& s);
 private:
  void worker();
  std::thread th_;
  std::mutex mu_;
  Query want_;
  bool have_want_ = false, done_ = false, more_ = false;
  std::vector<std::string> clicks_;
  std::vector<Station> result_;
  std::string msg_, data_dir_;
  int result_offset_ = 0;
  std::atomic<bool> quit_{false};
  std::atomic<bool> favs_dirty_{false};
  std::vector<Station> favs_copy_;
};

}  // namespace et
