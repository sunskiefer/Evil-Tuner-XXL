// Evil Tuner XXL -- radio transport repro: drives the WRAPPER (vst2_wrap.c) the way MPC delivers a
// tap on a drawn button (Live III, docs/NOTES.md: two presses 30-140 ms apart, then the wrapper's
// own spring-back to 0), against a real local stream, and checks the radio actually stops and starts.
//
//   radio_tap <url>            e.g. http://127.0.0.1:18766/test.mp3 (test/run_tap_repro.sh serves one)
//
// Checks (all through the wrapper, engine LEDs read back like MPC's Toggle Switches do):
//   1. tap PLAY  -> PLAYING status and audible output;
//   2. tap STOP  -> silence, stream torn down;
//   3. tap PLAY, then STOP ~0.3 s later, then PLAY ~0.3 s later -> PLAYING again;
//   4. a fast second tap on PLAY (~0.1 s) is one start, not a restart loop.
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <pthread.h>
#include <unistd.h>
#include "params.h"

typedef struct AEffect AEffect;
typedef intptr_t (*cb)(AEffect *, int32_t, int32_t, intptr_t, void *, float);
struct AEffect {
    int32_t magic;
    intptr_t (*d)(AEffect *, int32_t, int32_t, intptr_t, void *, float);
    void *p;
    void (*setP)(AEffect *, int32_t, float);
    float (*getP)(AEffect *, int32_t);
    int32_t np, npar, ni, no, flags;
    intptr_t r1, r2;
    int32_t a, b, c;
    float io;
    void *obj, *user;
    int32_t uid, ver;
    void (*pr)(AEffect *, float **, float **, int32_t);
    void *pdr;
    char f[56];
};
extern AEffect *VSTPluginMain(cb);

static double ti[16];
static intptr_t host(AEffect *e, int32_t op, int32_t i, intptr_t v, void *p, float o) {
    (void)e; (void)i; (void)v; (void)p; (void)o;
    if (op == 7) { ti[4] = 120.0; ((int32_t *)&ti[8])[5] = 1 << 10; return (intptr_t)ti; }
    return 0;
}

static int fails = 0;
#define CHECK(c, ...) do { printf("%s ", (c) ? "ok  " : "FAIL"); printf(__VA_ARGS__); printf("\n"); if (!(c)) fails++; } while (0)

static int find_param(const char *key) {
    for (int i = 0; i < NPARAMS; i++)
        if (!strcmp(PARAMS[i].key, key)) return i;
    return -1;
}

/* ---- audio thread: the host's processReplacing, in real time so housekeeping/polls and the debounce
 * clock (CLOCK_MONOTONIC in the wrapper) behave like on the device ---- */
static AEffect *fx;
static volatile int running = 1;
static double win_sum;
static long win_n;
static void *audio(void *arg) {
    (void)arg;
    float L[128], R[128], *o[2] = {L, R};
    while (running) {
        memset(L, 0, sizeof L); memset(R, 0, sizeof R);
        fx->pr(fx, 0, o, 128);
        for (int i = 0; i < 128; i++) { win_sum += L[i] * L[i] + R[i] * R[i]; win_n += 2; }
        usleep(2900);   /* 128 frames at 44100 Hz */
    }
    return 0;
}
static double window_rms(void) {   /* rms of the audio since the last call */
    double r = win_n ? sqrt(win_sum / win_n) : 0;
    win_sum = 0; win_n = 0;
    return r;
}
/* like MPC's UI thread: parameter writes land between audio blocks */
static void settle(int ms) { usleep(ms * 1000); }

/* one tap on a drawn button, the way MPC delivers it: press, a duplicate press 30-140 ms later, then
 * the spring-back to 0 (the wrapper's holdFrames echo) */
static void tap(AEffect *a, int i) {
    a->setP(a, i, 1.0f);
    settle(60);
    a->setP(a, i, 1.0f);
    settle(20);
    a->setP(a, i, 0.0f);
}

static char disp[64];
static const char *display(AEffect *a, int i) {   /* effGetParamDisplay: the engine's own text */
    disp[0] = 0;
    a->d(a, 7 /* effGetParamDisplay */, i, 0, disp, 0);
    return disp;
}
static int led(AEffect *a, int i) { return a->getP(a, i) > 0.5f; }
static int state_word(AEffect *a, int pinfo, const char *word) {   /* st_info ends with PLAYING / STOPPED / ... */
    return strstr(display(a, pinfo), word) != NULL;
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: radio_tap <stream url>\n"); return 2; }
    char chunk[1024];
    snprintf(chunk, sizeof chunk,
             "evil-tuner-xxl 1\ns\trepro-uuid\tREPRO STATION\t%s\tmp3\t128\tALL\n", argv[1]);
    AEffect *a = VSTPluginMain(host);
    if (!a) { printf("FAIL VSTPluginMain\n"); return 1; }
    fx = a;
    if (a->d(a, 24 /* effSetChunk */, 0, (intptr_t)strlen(chunk) + 1, chunk, 0) <= 0) {
        printf("FAIL effSetChunk\n"); return 1;
    }
    int pplay = find_param("play"), pstop = find_param("stop"), psync = find_param("sync");
    int pinfo = find_param("st_info");
    printf("initial st_info: \"%s\"\n", display(a, pinfo));
    printf("params: play=%d stop=%d sync=%d (momentary %d/%d/%d debounce %d/%d/%d)\n", pplay, pstop, psync,
           PARAMS[pplay].momentary, PARAMS[pstop].momentary, PARAMS[psync].momentary,
           PARAMS[pplay].debounce_ms, PARAMS[pstop].debounce_ms, PARAMS[psync].debounce_ms);

    pthread_t th;
    pthread_create(&th, 0, audio, 0);

    /* 1. tap PLAY: within ~4 s the state must reach PLAYING and sound must flow */
    settle(300);
    window_rms();
    tap(a, pplay);
    int playing = 0;
    for (int s = 0; s < 4; s++) { settle(1000); if (state_word(a, pinfo, "PLAYING")) { playing = 1; break; } }
    CHECK(playing, "tap PLAY -> st_info \"%s\" (want PLAYING)", display(a, pinfo));
    double r = window_rms();
    CHECK(r > 0.01, "tap PLAY -> audible output, rms %.4f", r);
    double play_rms = r;

    /* 2. tap STOP: the stream is torn down - output collapses (the delay/verb tail decays), PLAY's LED off */
    tap(a, pstop);
    settle(1200);
    r = window_rms();
    CHECK(r < play_rms * 0.25, "tap STOP -> output collapsing, rms %.4f (was %.4f)", r, play_rms);
    settle(2500);
    r = window_rms();
    CHECK(r < 0.001, "tap STOP -> tail decayed, rms %.4f", r);
    CHECK(!led(a, pplay), "tap STOP -> play LED off (getP %.2f)", a->getP(a, pplay));
    CHECK(state_word(a, pinfo, "STOPPED"), "tap STOP -> st_info \"%s\" (want STOPPED)", display(a, pinfo));

    /* 3. PLAY -> STOP -> PLAY, ~0.3 s apart (a stop+start inside any plausible debounce window) */
    tap(a, pplay); settle(300);
    tap(a, pstop); settle(300);
    tap(a, pplay);
    playing = 0;
    for (int s = 0; s < 4; s++) { settle(1000); if (state_word(a, pinfo, "PLAYING")) { playing = 1; break; } }
    CHECK(playing, "PLAY,STOP,PLAY quickly -> st_info \"%s\" (want PLAYING)", display(a, pinfo));
    settle(500);
    r = window_rms();
    CHECK(r > 0.01, "PLAY,STOP,PLAY quickly -> audible output, rms %.4f", r);

    /* 4. a fast second tap (~0.1 s, MPC's own duplicate included) starts, not restarts/stops */
    tap(a, pstop);
    settle(800);
    tap(a, pplay);
    settle(100);
    tap(a, pplay);   /* an impatient second tap: still one stream, still PLAYING */
    playing = 0;
    for (int s = 0; s < 4; s++) { settle(1000); if (state_word(a, pinfo, "PLAYING")) { playing = 1; break; } }
    CHECK(playing, "double tap PLAY -> st_info \"%s\" (want PLAYING)", display(a, pinfo));

    settle(300);
    running = 0;
    pthread_join(th, 0);
    a->d(a, 1, 0, 0, 0, 0);
    printf(fails ? "FAILED (%d)\n" : "PASSED\n", fails);
    return fails ? 1 : 0;
}
