// Evil Tuner XXL -- offline test host: drives the engine through mpc_engine() like the wrapper does, renders to a WAV.
//
//   host <helper dir> <out.wav> <seconds> [key=value | press:<key> | at:<seconds> | url:<stream url> | kiwi:<host>:<port>
//        | note:<n>:<vel> | show:<key>] ...
//
// "url:" plays a stream through the real radio path (curl -> ffmpeg -> ring); the commands after "at:<s>" run at that time.
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <string>
#include <vector>

extern "C" {
#include "engine.h"
}

// the test host has no MPC: its "plugin folder" is the helper directory's parent (the engine looks in <dir>/bin)
std::string g_plugin_dir;

static void wav_header(FILE* f, uint32_t frames) {
  uint32_t data = frames * 4, rate = 44100, br = rate * 4;
  uint16_t fmt = 1, ch = 2, ba = 4, bits = 16;
  uint32_t sz = 36 + data, fsz = 16;
  fwrite("RIFF", 1, 4, f); fwrite(&sz, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f); fwrite(&fsz, 4, 1, f);
  fwrite(&fmt, 2, 1, f); fwrite(&ch, 2, 1, f); fwrite(&rate, 4, 1, f); fwrite(&br, 4, 1, f); fwrite(&ba, 2, 1, f);
  fwrite(&bits, 2, 1, f); fwrite("data", 1, 4, f); fwrite(&data, 4, 1, f);
}

extern "C" void et_test_set_station(void* inst, const char* url);
extern "C" void et_test_set_kiwi(void* inst, const char* host, int port);

int main(int argc, char** argv) {
  if (argc < 4) { fprintf(stderr, "usage: host <plugin dir> <out.wav> <seconds> [cmds]\n"); return 2; }
  setenv("ET_PLUGIN_DIR", argv[1], 1);
  const mpc_engine_t* e = mpc_engine();
  void* in = e->create("/tmp/et-test-data");
  if (!in) { fprintf(stderr, "create failed\n"); return 1; }
  double secs = atof(argv[3]);
  int blocks = (int)(secs * 44100 / 128);
  struct Cmd { int block; std::string c; };
  std::vector<Cmd> cmds;
  int at = 0;
  for (int i = 4; i < argc; ++i) {
    std::string c = argv[i];
    if (c.compare(0, 3, "at:") == 0) { at = (int)(atof(c.c_str() + 3) * 44100 / 128); continue; }
    cmds.push_back({at, c});
  }
  FILE* f = fopen(argv[2], "wb");
  wav_header(f, (uint32_t)blocks * 128);
  int16_t buf[256];
  double peak = 0, sum = 0;
  long n = 0;
  for (int b = 0; b < blocks; ++b) {
    for (auto& c : cmds) {
      if (c.block != b) continue;
      if (c.c.compare(0, 6, "press:") == 0) e->set_param(in, c.c.c_str() + 6, "1");
      else if (c.c.compare(0, 4, "url:") == 0) et_test_set_station(in, c.c.c_str() + 4);
      else if (c.c.compare(0, 5, "kiwi:") == 0) {   // kiwi:<host>:<port>
        std::string hp = c.c.substr(5);
        size_t co = hp.rfind(':');
        et_test_set_kiwi(in, hp.substr(0, co).c_str(), atoi(hp.c_str() + co + 1));
      }
      else if (c.c.compare(0, 5, "note:") == 0) {
        int nt = 60, vel = 100;
        sscanf(c.c.c_str() + 5, "%d:%d", &nt, &vel);
        uint8_t m[3] = {(uint8_t)(vel ? 0x90 : 0x80), (uint8_t)nt, (uint8_t)vel};
        e->midi(in, m, 3);
      } else if (c.c.compare(0, 5, "show:") == 0) {
        char t[256];
        int r = e->get_param(in, c.c.c_str() + 5, t, sizeof t);
        printf("[%.2fs] %s = %s\n", b * 128 / 44100.0, c.c.c_str() + 5, r > 0 ? t : "(none)");
      } else {
        size_t eq = c.c.find('=');
        if (eq != std::string::npos) e->set_param(in, c.c.substr(0, eq).c_str(), c.c.substr(eq + 1).c_str());
      }
    }
    e->song_pos(in, b * 128 / 44100.0 * 2.0, 120.0, 1, 128);
    e->render(in, buf, 128);
    for (int i = 0; i < 256; ++i) { double x = buf[i] / 32768.0; peak = fmax(peak, fabs(x)); sum += x * x; n++; }
    fwrite(buf, 2, 256, f);
    // the real thing renders in real time: let the source threads keep up
    if (b % 8 == 0) usleep(128 * 8 * 1000000 / 44100);
  }
  fclose(f);
  char t[256];
  const char* show[] = {"st_name", "st_title", "st_info", "page_txt", "kiwi_txt", "readout", "tape_txt", "row1", "row2", "view"};
  for (const char* k : show) if (e->get_param(in, k, t, sizeof t) > 0) printf("%-9s %s\n", k, t);
  printf("peak %.3f  rms %.4f\n", peak, sqrt(sum / (n ? n : 1)));
  e->destroy(in);
  return 0;
}
