// Evil Tuner XXL -- the sources: internet radio, PHONE (Roc) and AIRPLAY (KIWISDR is in kiwi.cc).
//
// One worker thread per instance owns whatever is playing. Every source ends up as raw 44.1 kHz stereo s16 on a pipe
// from a helper process (bin/ in the plugin's folder, all static):
//   RADIO    the stream is fetched here with MPC OS's libcurl (any https, redirects, ICY "now playing" titles) and fed
//            to ffmpeg's stdin; ffmpeg decodes it (mp3 / aac / ogg / flac) to its stdout
//   PHONE    et_roc listens for a Roc stream (Roc Droid) on udp 10001-10003
//   AIRPLAY  shairport-sync (classic AirPlay) advertises "Evil Tuner XXL" and plays to its stdout; its metadata pipe gives
//            the title
// A reader thread turns the pipe into floats in the ring; the audio thread only ever reads the ring. Helpers start
// through et_exec, which ties them to this thread's life (PR_SET_PDEATHSIG) and closes MPC's descriptors in them.
#include "et.h"
#include "curlx.h"

#include <arpa/inet.h>
#include <math.h>
#include <condition_variable>
#include <errno.h>
#include <fcntl.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <pthread.h>
#include <signal.h>
#include <spawn.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

extern char** environ;

namespace et {


static void logf(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static void logf(const char* fmt, ...) {
  static std::mutex m;
  std::lock_guard<std::mutex> lk(m);
  FILE* f = fopen("/tmp/eviltuner.log", "a");
  if (!f) return;
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  fprintf(f, "%ld.%03ld ", (long)ts.tv_sec, ts.tv_nsec / 1000000);
  va_list ap;
  va_start(ap, fmt);
  vfprintf(f, fmt, ap);
  va_end(ap);
  fputc('\n', f);
  fclose(f);
}

void log_line(const char* fmt, ...) {
  char b[512];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(b, sizeof b, fmt, ap);
  va_end(ap);
  logf("%s", b);
}

// ------------------------------------------------------------------------------------------------ child processes
struct Child {
  pid_t pid = -1;
  int in = -1, out = -1;   // our ends: its stdin (write), its stdout (read)
};

// argv[0] is the program; started as `et_exec <program> args...` with MPC's LD_PRELOAD (MockbaMod) left out of its
// environment, stdin / stdout as pipes when asked, stderr to /tmp/eviltuner-<name>.log
static bool spawn(const std::string& dir, const std::vector<std::string>& args, bool want_in, Child& c,
                  const char* logname) {
  int pin[2] = {-1, -1}, pout[2] = {-1, -1};
  if (want_in && pipe2(pin, O_CLOEXEC) != 0) return false;
  if (pipe2(pout, O_CLOEXEC) != 0) {
    if (want_in) { close(pin[0]); close(pin[1]); }
    return false;
  }
  char logpath[128];
  snprintf(logpath, sizeof logpath, "/tmp/eviltuner-%s.log", logname);
  int errfd = open(logpath, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
  posix_spawn_file_actions_t fa;
  posix_spawn_file_actions_init(&fa);
  if (want_in) posix_spawn_file_actions_adddup2(&fa, pin[0], 0);
  else posix_spawn_file_actions_addopen(&fa, 0, "/dev/null", O_RDONLY, 0);
  posix_spawn_file_actions_adddup2(&fa, pout[1], 1);
  if (errfd >= 0) posix_spawn_file_actions_adddup2(&fa, errfd, 2);
  posix_spawnattr_t at;
  posix_spawnattr_init(&at);
  sigset_t none, dflt;
  sigemptyset(&none);
  sigemptyset(&dflt);
  sigaddset(&dflt, SIGPIPE);
  sigaddset(&dflt, SIGCHLD);
  sigaddset(&dflt, SIGTERM);
  sigaddset(&dflt, SIGINT);
  posix_spawnattr_setsigmask(&at, &none);
  posix_spawnattr_setsigdefault(&at, &dflt);
  posix_spawnattr_setflags(&at, POSIX_SPAWN_SETSIGMASK | POSIX_SPAWN_SETSIGDEF);
  std::vector<std::string> full;
  full.push_back(dir + "/et_exec");
  full.push_back(dir + "/" + args[0]);
  for (size_t i = 1; i < args.size(); ++i) full.push_back(args[i]);
  std::vector<char*> av;
  for (auto& s : full) av.push_back(const_cast<char*>(s.c_str()));
  av.push_back(nullptr);
  std::vector<char*> env;
  for (char** e = environ; e && *e; ++e)
    if (strncmp(*e, "LD_PRELOAD=", 11) != 0) env.push_back(*e);
  env.push_back(nullptr);
  pid_t pid = -1;
  int rc = posix_spawn(&pid, av[0], &fa, &at, av.data(), env.data());
  posix_spawn_file_actions_destroy(&fa);
  posix_spawnattr_destroy(&at);
  if (errfd >= 0) close(errfd);
  if (want_in) close(pin[0]);
  close(pout[1]);
  if (rc != 0) {
    logf("spawn %s failed: %s", full[1].c_str(), strerror(rc));
    if (want_in) close(pin[1]);
    close(pout[0]);
    return false;
  }
  c.pid = pid;
  c.in = want_in ? pin[1] : -1;
  c.out = pout[0];
  logf("spawned %s pid %d", full[1].c_str(), (int)pid);
  return true;
}

static void end_child(Child& c) {
  if (c.in >= 0) { close(c.in); c.in = -1; }
  if (c.pid > 0) {
    kill(c.pid, SIGTERM);
    for (int i = 0; i < 40; ++i) {   // up to 0.4 s, then SIGKILL
      if (waitpid(c.pid, nullptr, WNOHANG) == c.pid) { c.pid = -1; break; }
      usleep(10000);
    }
    if (c.pid > 0) {
      kill(c.pid, SIGKILL);
      waitpid(c.pid, nullptr, 0);
      c.pid = -1;
    }
  }
  if (c.out >= 0) { close(c.out); c.out = -1; }
}

// A write to a pipe whose reader died must fail with EPIPE, not raise SIGPIPE (whose default ends MPC): the source
// threads block it (a synchronous signal goes to the thread that wrote).
static void block_sigpipe() {
  sigset_t s;
  sigemptyset(&s);
  sigaddset(&s, SIGPIPE);
  pthread_sigmask(SIG_BLOCK, &s, nullptr);
}

// ------------------------------------------------------------------------------------------------ pipe -> ring
// Reads s16 stereo from fd into the ring until EOF or `stop`; blocks (sleeps) while the ring is full, which holds the
// child back (it holds curl back in turn). Returns the frames read.
template <class Stop>
static uint64_t pump(int fd, Ring& ring, Stop stop) {
  int16_t raw[2048];
  float f[2048];
  size_t have = 0;   // bytes in raw
  uint64_t total = 0;
  for (;;) {
    if (stop()) break;
    size_t room = have < sizeof raw ? sizeof raw - have : 0;
    ssize_t n = room ? read(fd, reinterpret_cast<char*>(raw) + have, room) : 0;
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) break;
    have += (size_t)n;
    size_t frames = have / 4;
    for (size_t i = 0; i < frames * 2; ++i) f[i] = raw[i] * (1.f / 32768.f);
    size_t done = 0;
    while (done < frames && !stop()) {
      done += ring.write(f + done * 2, (uint32_t)(frames - done));
      if (done < frames) usleep(5000);
    }
    total += frames;
    size_t rest = have - frames * 4;
    if (rest) memmove(raw, reinterpret_cast<char*>(raw) + frames * 4, rest);
    have = rest;
  }
  return total;
}

// ------------------------------------------------------------------------------------------------ the radio fetch
struct Fetch {
  Sources* src;
  uint32_t gen;
  std::atomic<uint32_t>* cur_gen;
  std::atomic<bool>* quit;
  int ffin = -1;               // ffmpeg's stdin
  long metaint = 0;            // ICY: audio bytes between metadata blocks
  long until_meta = 0;
  int meta_len = -1;           // -1: next byte is the length byte
  std::string meta;
  std::string content_type;
  bool playlist = false;       // the body is a .pls / .m3u: collected, not played
  std::string body;
  uint64_t audio_bytes = 0;
  std::string title;
};

static size_t on_header(char* p, size_t sz, size_t n, void* ud) {
  Fetch* f = static_cast<Fetch*>(ud);
  std::string h(p, sz * n);
  std::string low = h;
  for (auto& ch : low) ch = (char)tolower((unsigned char)ch);
  if (low.compare(0, 12, "icy-metaint:") == 0) f->metaint = atol(h.c_str() + 12);
  if (low.compare(0, 13, "content-type:") == 0) {
    f->content_type = low.substr(13);
    if (low.find("mpegurl") != std::string::npos || low.find("scpls") != std::string::npos ||
        low.find("x-pls") != std::string::npos || low.find("text/") != std::string::npos)
      f->playlist = true;
  }
  if (low.compare(0, 5, "http/") == 0) {   // a new response (after a redirect): forget the last one's headers
    f->metaint = 0;
    f->playlist = false;
    f->content_type.clear();
  }
  return sz * n;
}

static bool write_all(int fd, const char* p, size_t n) {
  while (n) {
    ssize_t w = write(fd, p, n);
    if (w < 0) {
      if (errno == EINTR) continue;
      return false;
    }
    p += w;
    n -= (size_t)w;
  }
  return true;
}

static void parse_icy(Fetch* f) {
  // StreamTitle='Artist - Title';StreamUrl='...';
  const char* k = strstr(f->meta.c_str(), "StreamTitle='");
  if (!k) return;
  k += 13;
  const char* e = strstr(k, "';");
  std::string t = e ? std::string(k, e - k) : std::string(k);
  while (!t.empty() && (t.back() == '\'' || t.back() == ' ' || t.back() == 0)) t.pop_back();
  f->title = t;
}

static size_t on_body(char* p, size_t sz, size_t n, void* ud) {
  Fetch* f = static_cast<Fetch*>(ud);
  size_t len = sz * n;
  if (f->playlist) {
    if (f->body.size() < 65536) f->body.append(p, len);
    return len;
  }
  if (!f->metaint) {
    if (!write_all(f->ffin, p, len)) return 0;
    f->audio_bytes += len;
    return len;
  }
  size_t i = 0;
  if (!f->until_meta && f->meta_len < 0 && f->audio_bytes == 0) f->until_meta = f->metaint;
  while (i < len) {
    if (f->meta_len < 0 && f->until_meta > 0) {          // audio
      size_t take = std::min((size_t)f->until_meta, len - i);
      if (!write_all(f->ffin, p + i, take)) return 0;
      f->audio_bytes += take;
      f->until_meta -= (long)take;
      i += take;
    } else if (f->meta_len < 0) {                         // the length byte
      f->meta_len = (unsigned char)p[i++] * 16;
      f->meta.clear();
      if (f->meta_len == 0) { f->meta_len = -1; f->until_meta = f->metaint; }
    } else {                                              // metadata
      size_t take = std::min((size_t)f->meta_len - f->meta.size(), len - i);
      f->meta.append(p + i, take);
      i += take;
      if ((int)f->meta.size() >= f->meta_len) {
        parse_icy(f);
        f->meta_len = -1;
        f->until_meta = f->metaint;
      }
    }
  }
  return len;
}

static int on_progress(void* ud, curl_off_t, curl_off_t, curl_off_t, curl_off_t) {
  Fetch* f = static_cast<Fetch*>(ud);
  if (f->quit->load() || f->cur_gen->load() != f->gen) return 1;   // a new request: abort
  return 0;
}

// the first stream URL in a .pls / .m3u body
static std::string playlist_url(const std::string& body) {
  size_t pos = 0;
  while (pos < body.size()) {
    size_t e = body.find_first_of("\r\n", pos);
    std::string line = body.substr(pos, e == std::string::npos ? std::string::npos : e - pos);
    pos = e == std::string::npos ? body.size() : e + 1;
    size_t eq = line.find('=');
    if (line.compare(0, 4, "File") == 0 && eq != std::string::npos) line = line.substr(eq + 1);
    while (!line.empty() && (line[0] == ' ' || line[0] == '\t')) line.erase(0, 1);
    if (line.compare(0, 7, "http://") == 0 || line.compare(0, 8, "https://") == 0) return line;
  }
  return "";
}

// ------------------------------------------------------------------------------------------------ runnable helpers
// The helpers must be executable where they are: a copy that lost its exec bits gets them back; a folder on a card
// mounted noexec (exFAT) is copied to /tmp (or the data folder) once, and run from there. No step for the user.
static bool can_exec_in(const std::string& dir) {
  struct statvfs v;
  if (statvfs(dir.c_str(), &v) == 0 && (v.f_flag & ST_NOEXEC)) return false;
  return access((dir + "/et_exec").c_str(), X_OK) == 0;
}

static bool copy_file(const std::string& a, const std::string& b) {
  FILE* in = fopen(a.c_str(), "rb");
  if (!in) return false;
  FILE* out = fopen(b.c_str(), "wb");
  if (!out) { fclose(in); return false; }
  char buf[65536];
  size_t n;
  bool ok = true;
  while ((n = fread(buf, 1, sizeof buf, in)) > 0) if (fwrite(buf, 1, n, out) != n) { ok = false; break; }
  fclose(in);
  if (fclose(out) != 0) ok = false;
  return ok && chmod(b.c_str(), 0755) == 0;
}

static std::string runnable_helpers(const std::string& dir, const std::string& data_dir) {
  static const char* kFiles[] = {"et_exec", "ffmpeg", "et_roc", "shairport-sync"};
  for (const char* f : kFiles) {
    std::string p = dir + "/" + f;
    if (access(p.c_str(), F_OK) == 0 && access(p.c_str(), X_OK) != 0) chmod(p.c_str(), 0755);
  }
  if (can_exec_in(dir)) return dir;
  std::vector<std::string> dests = {"/tmp/eviltuner-xxl-bin"};
  if (!data_dir.empty()) dests.push_back(data_dir + "/bin");
  for (auto& d : dests) {
    mkdir(d.c_str(), 0755);
    bool ok = true;
    for (const char* f : kFiles) ok = ok && copy_file(dir + "/" + f, d + "/" + f);
    if (ok && can_exec_in(d)) { logf("helpers run from %s", d.c_str()); return d; }
  }
  return dir;   // spawn reports the failure
}

// ------------------------------------------------------------------------------------------------ Sources
void Sources::start(const std::string& plugin_dir, const std::string& data_dir) {
  helper_dir = plugin_dir + "/bin";
  data_dir_ = data_dir;
  ring.init(1u << 19);   // 11.9 s
  quit_ = false;
  th_ = std::thread([this] { worker(); });
}

void Sources::stop_all() {
  quit_ = true;
  gen_++;
  cv_.notify_all();
  if (th_.joinable()) th_.join();
}

void Sources::play_radio(const Station& s) {
  std::lock_guard<std::mutex> lk(mu_);
  want_kind_ = SRC_RADIO;
  want_station_ = s;
  gen_++;
  cv_.notify_all();
}
void Sources::play_phone() {
  std::lock_guard<std::mutex> lk(mu_);
  want_kind_ = SRC_PHONE;
  gen_++;
  cv_.notify_all();
}
void Sources::play_airplay() {
  std::lock_guard<std::mutex> lk(mu_);
  want_kind_ = SRC_AIRPLAY;
  gen_++;
  cv_.notify_all();
}
void Sources::play_kiwi(const KiwiRx& rx, const KiwiTune& t) {
  kiwi_tune(t);
  std::lock_guard<std::mutex> lk(mu_);
  want_kind_ = SRC_KIWI;
  want_rx_ = rx;
  gen_++;
  cv_.notify_all();
}
void Sources::kiwi_tune(const KiwiTune& t) {
  uint32_t q = tune_seq_.load(std::memory_order_relaxed);
  tune_seq_.store(q + 1, std::memory_order_release);   // odd: being written
  std::atomic_thread_fence(std::memory_order_release);
  tune_hz_.store((int64_t)llround(t.khz * 1000.0), std::memory_order_relaxed);
  tune_mode_.store(t.mode, std::memory_order_relaxed);
  tune_lo_.store(t.lo, std::memory_order_relaxed);
  tune_hi_.store(t.hi, std::memory_order_relaxed);
  tune_seq_.store(q + 2, std::memory_order_release);
}
bool Sources::kiwi_tune_read(KiwiTune& t, uint32_t& rev) {
  for (int tries = 0; tries < 100; ++tries) {
    uint32_t a = tune_seq_.load(std::memory_order_acquire);
    if (a & 1) continue;
    KiwiTune x;
    x.khz = tune_hz_.load(std::memory_order_relaxed) / 1000.0;
    x.mode = tune_mode_.load(std::memory_order_relaxed);
    x.lo = tune_lo_.load(std::memory_order_relaxed);
    x.hi = tune_hi_.load(std::memory_order_relaxed);
    std::atomic_thread_fence(std::memory_order_acquire);
    if (tune_seq_.load(std::memory_order_relaxed) != a) continue;
    bool changed = a != rev;
    rev = a;
    t = x;
    return changed;
  }
  return false;
}
void Sources::stop() {
  std::lock_guard<std::mutex> lk(mu_);
  want_kind_ = SRC_NONE;
  gen_++;
  cv_.notify_all();
}

void Sources::set_title(const std::string& t) {
  std::lock_guard<std::mutex> lk(mu_);
  if (t == title_) return;
  title_ = t;
  title_new_ = true;
  title_rev++;
}
void Sources::set_status(const std::string& t) {
  std::lock_guard<std::mutex> lk(mu_);
  if (t == status_) return;
  status_ = t;
  status_new_ = true;
  logf("status: %s", t.c_str());
}
bool Sources::title(std::string& out) {
  std::unique_lock<std::mutex> lk(mu_, std::try_to_lock);
  if (!lk.owns_lock() || !title_new_) return false;
  out = title_;
  title_new_ = false;
  return true;
}
bool Sources::status(std::string& out) {
  std::unique_lock<std::mutex> lk(mu_, std::try_to_lock);
  if (!lk.owns_lock() || !status_new_) return false;
  out = status_;
  status_new_ = false;
  return true;
}

std::string Sources::ip_text() {
  struct ifaddrs* ifs = nullptr;
  std::string out;
  if (getifaddrs(&ifs) != 0) return "";
  for (struct ifaddrs* i = ifs; i; i = i->ifa_next) {
    if (!i->ifa_addr || i->ifa_addr->sa_family != AF_INET) continue;
    if (i->ifa_flags & IFF_LOOPBACK) continue;
    if (!(i->ifa_flags & IFF_UP)) continue;
    char b[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &((struct sockaddr_in*)i->ifa_addr)->sin_addr, b, sizeof b);
    if (!out.empty()) out += "  ";
    out += b;
  }
  freeifaddrs(ifs);
  return out;
}

void Sources::worker() {
  block_sigpipe();
  helper_dir = runnable_helpers(helper_dir, data_dir_);
  for (;;) {
    int kind;
    Station st;
    KiwiRx rx;
    uint32_t g;
    {
      std::unique_lock<std::mutex> lk(mu_);
      g = gen_.load();
      kind = want_kind_;
      st = want_station_;
      rx = want_rx_;
    }
    if (quit_.load()) break;
    this->kind = kind;
    ring.clear();
    if (kind == SRC_RADIO) run_radio(st, g);
    else if (kind == SRC_PHONE || kind == SRC_AIRPLAY) run_child(kind, g);
    else if (kind == SRC_KIWI) run_kiwi(rx, g);
    else { state = 0; }
    // wait for the next request (a source that ended by itself idles here)
    std::unique_lock<std::mutex> lk(mu_);
    if (gen_.load() == g && !quit_.load()) {
      if (kind != SRC_NONE && state != 4) state = 0;
      cv_.wait(lk, [&] { return gen_.load() != g || quit_.load(); });
    }
    if (quit_.load()) break;
  }
  state = 0;
}

void Sources::run_radio(const Station& s, uint32_t g) {
  CurlApi& cu = curl();
  if (!cu.ok) {
    state = 4;
    set_status("NO LIBCURL ON THIS DEVICE");
    return;
  }
  set_title("");
  std::string url = s.url;
  int attempts = 0;
  while (!quit_.load() && gen_.load() == g) {
    state = 1;
    set_status(attempts ? "RECONNECTING" : "CONNECTING");
    Child ff;
    std::vector<std::string> args = {"ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-probesize", "65536",
                                     "-i", "pipe:0", "-vn", "-f", "s16le", "-ac", "2", "-ar", "44100", "pipe:1"};
    if (!spawn(helper_dir, args, true, ff, "ffmpeg")) {
      state = 4;
      set_status("CAN'T START THE DECODER");
      return;
    }
    std::atomic<bool> stop_pump{false};
    std::atomic<uint64_t> got{0};
    pid_t ffpid = ff.pid;
    std::thread reader([&] {
      block_sigpipe();
      got = pump(ff.out, ring, [&] { return stop_pump.load() || quit_.load() || gen_.load() != g; });
      if (quit_.load() || gen_.load() != g) kill(ffpid, SIGKILL);   // a write blocked in the fetch now fails: it ends
    });
    Fetch f;
    f.src = this;
    f.gen = g;
    f.cur_gen = &gen_;
    f.quit = &quit_;
    f.ffin = ff.in;
    CURL* c = cu.easy_init();
    struct curl_slist* hdr = cu.slist_append(nullptr, "Icy-MetaData: 1");
    curl_common(c, 10);
    cu.easy_setopt(c, CURLOPT_URL, url.c_str());
    cu.easy_setopt(c, CURLOPT_HTTPHEADER, hdr);
    cu.easy_setopt(c, CURLOPT_HEADERFUNCTION, on_header);
    cu.easy_setopt(c, CURLOPT_HEADERDATA, &f);
    cu.easy_setopt(c, CURLOPT_WRITEFUNCTION, on_body);
    cu.easy_setopt(c, CURLOPT_WRITEDATA, &f);
    cu.easy_setopt(c, CURLOPT_NOPROGRESS, 0L);
    cu.easy_setopt(c, CURLOPT_XFERINFOFUNCTION, on_progress);
    cu.easy_setopt(c, CURLOPT_XFERINFODATA, &f);
    cu.easy_setopt(c, CURLOPT_LOW_SPEED_LIMIT, 1000L);   // stalled for 15 s: reconnect
    cu.easy_setopt(c, CURLOPT_LOW_SPEED_TIME, 15L);
    // the ICY title is parsed on this (the fetch) thread; the progress callback, also on this thread, publishes it
    struct Pub {
      static int progress(void* ud, curl_off_t a, curl_off_t b, curl_off_t c2, curl_off_t d) {
        Fetch* ff2 = static_cast<Fetch*>(ud);
        if (!ff2->title.empty()) ff2->src->set_title(ff2->title);
        if (ff2->src->state.load() != 3 && ff2->src->ring.w.load() != 0) {
          ff2->src->state = 3;
          ff2->src->set_status("PLAYING");
        }
        return on_progress(ud, a, b, c2, d);
      }
    };
    cu.easy_setopt(c, CURLOPT_XFERINFOFUNCTION, Pub::progress);
    state = 2;
    set_status("BUFFERING");
    CURLcode rc = cu.easy_perform(c);
    long code = 0;
    cu.easy_getinfo(c, CURLINFO_RESPONSE_CODE, &code);
    cu.easy_cleanup(c);
    cu.slist_free_all(hdr);
    // the decoder drains what it has, then ends
    close(ff.in);
    ff.in = -1;
    bool aborted = quit_.load() || gen_.load() != g;
    if (aborted) stop_pump = true;
    {
      // give the reader up to 1 s to finish the tail, then end the decoder
      for (int i = 0; i < 100 && !aborted; ++i) {
        if (waitpid(ff.pid, nullptr, WNOHANG) == ff.pid) { ff.pid = -1; break; }
        usleep(10000);
      }
    }
    stop_pump = true;
    end_child(ff);
    reader.join();
    if (aborted) return;
    if (code >= 400) {
      state = 4;
      char b[64];
      snprintf(b, sizeof b, "STATION ERROR %ld", code);
      set_status(b);
      return;
    }
    if (f.playlist) {
      std::string next = playlist_url(f.body);
      if (!next.empty() && attempts < 4) {
        logf("playlist -> %s", next.c_str());
        url = next;
        attempts++;
        continue;
      }
      state = 4;
      set_status("NOT A STREAM (PLAYLIST)");
      return;
    }
    if (code >= 400) {
      state = 4;
      char b[64];
      snprintf(b, sizeof b, "STATION ERROR %ld", code);
      set_status(b);
      return;
    }
    if (got.load() == 0 && f.audio_bytes > 0) {
      state = 4;
      set_status("CAN'T DECODE THIS STATION");
      return;
    }
    logf("stream ended: %s (code %ld, %llu bytes)", cu.easy_strerror(rc), code, (unsigned long long)f.audio_bytes);
    if (++attempts > 6) {
      state = 4;
      set_status(rc == CURLE_OK ? "STREAM ENDED" : "NO CONNECTION");
      return;
    }
    // reconnect after a short wait (the network dropped, the station restarted)
    for (int i = 0; i < 20 && !quit_.load() && gen_.load() == g; ++i) usleep(100000);
  }
}

static std::string b64dec(const std::string& in) {
  static const std::string tbl = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  std::string out;
  int val = 0, bits = -8;
  for (unsigned char ch : in) {
    size_t p = tbl.find(ch);
    if (p == std::string::npos) continue;
    val = (val << 6) + (int)p;
    bits += 6;
    if (bits >= 0) {
      out.push_back(char((val >> bits) & 0xFF));
      bits -= 8;
    }
  }
  return out;
}

static std::string tagval(const std::string& s, const char* open, const char* close) {
  size_t a = s.find(open);
  if (a == std::string::npos) return "";
  a = s.find('>', a);
  if (a == std::string::npos) return "";
  size_t b = s.find(close, a);
  if (b == std::string::npos) return "";
  return s.substr(a + 1, b - a - 1);
}

void Sources::run_child(int kind, uint32_t g) {
  Child ch;
  std::vector<std::string> args;
  std::string meta_pipe;
  set_title("");
  if (kind == SRC_PHONE) {
    args = {"et_roc", "10001"};
  } else {
    // shairport-sync's settings, written each time (the name the iPhone shows is "Evil Tuner XXL")
    meta_pipe = "/tmp/eviltuner-airplay-meta";
    std::string conf = data_dir_.empty() ? "/tmp/eviltuner-airplay.conf" : data_dir_ + "/airplay.conf";
    FILE* f = fopen(conf.c_str(), "w");
    if (f) {
      fprintf(f,
              "general = {\n  name = \"Evil Tuner XXL\";\n  port = 5000;\n  udp_port_base = 6001;\n"
              "  output_backend = \"stdout\";\n  mdns_backend = \"tinysvcmdns\";\n  interpolation = \"basic\";\n"
              "  ignore_volume_control = \"yes\";\n};\n"
              "sessioncontrol = {\n  allow_session_interruption = \"yes\";\n  session_timeout = 20;\n};\n"
              "metadata = {\n  enabled = \"yes\";\n  include_cover_art = \"no\";\n  pipe_name = \"%s\";\n"
              "  pipe_timeout = 2000;\n};\n",
              meta_pipe.c_str());
      fclose(f);
    }
    unlink(meta_pipe.c_str());
    mkfifo(meta_pipe.c_str(), 0644);
    args = {"shairport-sync", "-c", conf, "-o", "stdout"};
  }
  state = 1;
  set_status(kind == SRC_PHONE ? "WAITING FOR THE PHONE" : "WAITING FOR AIRPLAY");
  if (!spawn(helper_dir, args, false, ch, kind == SRC_PHONE ? "roc" : "airplay")) {
    state = 4;
    set_status("CAN'T START THE RECEIVER");
    return;
  }
  std::atomic<bool> stop_pump{false};
  std::thread reader([&] {
    block_sigpipe();
    pump(ch.out, ring, [&] { return stop_pump.load() || quit_.load() || gen_.load() != g; });
  });
  std::thread meta;
  int meta_fd = -1;
  if (!meta_pipe.empty()) {
    meta_fd = open(meta_pipe.c_str(), O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    meta = std::thread([&, this] {
      std::string buf, artist, track;
      char tmp[4096];
      while (!stop_pump.load()) {
        ssize_t n = meta_fd >= 0 ? read(meta_fd, tmp, sizeof tmp) : -1;
        if (n <= 0) { usleep(100000); continue; }
        buf.append(tmp, (size_t)n);
        size_t e;
        while ((e = buf.find("</item>")) != std::string::npos) {
          std::string item = buf.substr(0, e + 7);
          buf.erase(0, e + 7);
          std::string type = tagval(item, "<type>", "</type>"), code = tagval(item, "<code>", "</code>");
          if (type != "636f7265") continue;   // 'core'
          std::string data = b64dec(tagval(item, "<data", "</data>"));
          if (code == "6d696e6d") track = data;        // 'minm': the title
          else if (code == "61736172") artist = data;  // 'asar': the artist
          else continue;
          set_title(artist.empty() ? track : track.empty() ? artist : artist + " - " + track);
        }
        if (buf.size() > 65536) buf.clear();
      }
    });
  }
  // watch: playing once audio flows, end with the request or the child
  uint32_t last_fill = 0;
  int quiet = 0;
  while (!quit_.load() && gen_.load() == g) {
    usleep(100000);
    if (waitpid(ch.pid, nullptr, WNOHANG) == ch.pid) {
      ch.pid = -1;
      state = 4;
      set_status(kind == SRC_PHONE ? "PHONE RECEIVER STOPPED (PORT IN USE?)" : "AIRPLAY STOPPED (PORT IN USE?)");
      break;
    }
    uint32_t w = ring.w.load();
    if (w != last_fill) { last_fill = w; quiet = 0; if (state != 3) { state = 3; set_status(kind == SRC_PHONE ? "PHONE CONNECTED" : "AIRPLAY CONNECTED"); } }
    else if (++quiet > 30 && state == 3) { state = 1; set_status(kind == SRC_PHONE ? "WAITING FOR THE PHONE" : "WAITING FOR AIRPLAY"); }
  }
  stop_pump = true;
  end_child(ch);
  reader.join();
  if (meta.joinable()) meta.join();
  if (meta_fd >= 0) close(meta_fd);
  if (!meta_pipe.empty()) unlink(meta_pipe.c_str());
}

}  // namespace et
