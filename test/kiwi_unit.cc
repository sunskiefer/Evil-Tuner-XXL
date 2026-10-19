// Evil Tuner XXL -- KIWISDR unit checks: the user's list lines, a receiver's /status, the built-in list.
#include <stdio.h>
#include <string.h>

#include "et.h"

using namespace et;

static int fails = 0;
#define CHECK(c) do { if (!(c)) { printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #c); fails++; } } while (0)

int main() {
  KiwiRx r;
  CHECK(KiwiDir::parse_line("http://pallas-kiwi.ddns.net:8073 pallas, lapland", r));
  CHECK(r.host == "pallas-kiwi.ddns.net" && r.port == 8073 && r.path.empty() && r.name == "PALLAS, LAPLAND" && r.user);
  CHECK(KiwiDir::parse_line("  my-kiwi.example.org  ", r));
  CHECK(r.host == "my-kiwi.example.org" && r.port == 8073 && r.name == "MY-KIWI.EXAMPLE.ORG");
  CHECK(KiwiDir::parse_line("http://hallmann.selfhost.eu/ MAINZ", r));   // a browser address without a port: 80
  CHECK(r.host == "hallmann.selfhost.eu" && r.port == 80 && r.path.empty());
  CHECK(KiwiDir::parse_line("http://example.org:8080/kw/ GRAZ  # behind a web server", r));
  CHECK(r.port == 8080 && r.path == "/kw" && r.name == "GRAZ");
  CHECK(KiwiDir::parse_line("10.0.0.5:8074", r) && r.host == "10.0.0.5" && r.port == 8074);
  CHECK(!KiwiDir::parse_line("https://kiwi.example.org/ TLS ONLY", r));
  CHECK(!KiwiDir::parse_line("# a comment", r));
  CHECK(!KiwiDir::parse_line("   ", r));
  CHECK(!KiwiDir::parse_line("host:99999", r));

  KiwiRx s;
  KiwiDir::parse_status("status=active\noffline=no\nname=X\nusers=3\nusers_max=8\nbands=0-30000000\n", s);
  CHECK(s.users == 3 && s.users_max == 8 && !s.offline);
  KiwiRx o;
  KiwiDir::parse_status("status=offline\r\noffline=yes\r\nusers=0\r\nusers_max=4\r\n", o);
  CHECK(o.offline && o.users == 0 && o.users_max == 4);

  auto b = KiwiDir::builtin();
  CHECK(b.size() >= 30);
  for (auto& k : b) CHECK(!k.host.empty() && k.port > 0 && !k.name.empty() && k.loc.size() == 2);
  for (size_t i = 0; i < b.size(); ++i)
    for (size_t j = i + 1; j < b.size(); ++j) CHECK(b[i].id() != b[j].id());

  CHECK(!strcmp(kiwi_mode_word(0), "am") && !strcmp(kiwi_mode_word(4), "nbfm") && !strcmp(kiwi_mode_word(99), "am"));
  printf("kiwi unit: %s\n", fails ? "FAIL" : "ok");
  return fails ? 1 : 0;
}
