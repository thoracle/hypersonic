#!/usr/bin/env python3
"""Generate four QA stress-test tracks with deliberately OPPOSED musical
footprints, so track differentiation is testable end to end:

  qa-thrash     percussive-dominant, 176 BPM, compressed-loud, low riffs
  qa-drift      tonal-dominant ambient, quiet, sparse, high register (Ab)
  qa-funk       balanced syncopated groove, 104 BPM, drums-out breakdown
  qa-crescendo  orchestral arc: pp strings -> ff climax (one hottest section)

Deterministic (fixed LCG, no wall-clock). Pure numpy -> WAV; ffmpeg -> mp3.
Dev tool only — never imported by the game. Run with any python + numpy:

  python3 tools/make_qa_tracks.py [outdir=tracks]
"""
import numpy as np, wave, subprocess, sys, os

SR = 44100

# ---------------- deterministic LCG (no numpy RandomState drift) ----------
class LCG:
    def __init__(self, seed): self.s = seed % 2147483647 or 1
    def next(self):
        self.s = (self.s * 48271) % 2147483647
        return self.s / 2147483647.0

def t2s(t): return int(round(t * SR))
def midi(n): return 440.0 * 2 ** ((n - 69) / 12.0)

# ---------------- primitives ----------------------------------------------
def _noise(n, seed):
    r = LCG(seed); out = np.empty(n)
    # vectorized LCG: generate via numpy int math (same recurrence)
    s = np.empty(n, dtype=np.int64); acc = r.s
    for i in range(n):  # fallback only for tiny n
        acc = (acc * 48271) % 2147483647; s[i] = acc
    return s / 2147483647.0 * 2 - 1

_noise_pool = None
def noise(n, seed=1):
    """Cheap deterministic noise: one big precomputed pool, offset by seed."""
    global _noise_pool
    if _noise_pool is None:
        acc = 12345; N = SR * 3
        vals = np.empty(N)
        for i in range(N):
            acc = (acc * 48271) % 2147483647
            vals[i] = acc
        _noise_pool = vals / 2147483647.0 * 2 - 1
    off = (seed * 7919) % (len(_noise_pool) - 1)
    reps = int(np.ceil((off + n) / len(_noise_pool))) + 1
    return np.tile(_noise_pool, reps)[off:off + n]

def lp(x, cutoff):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f); hi = f > cutoff
    m[hi] = np.exp(-(f[hi] - cutoff) / (cutoff * 0.6 + 1e-9))
    return np.fft.irfft(X * m, len(x))

def hp(x, cutoff):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f); lo = f < cutoff
    m[lo] = np.exp(-(cutoff - f[lo]) / (cutoff * 0.35 + 1e-9))
    return np.fft.irfft(X * m, len(x))

def env_ad(n, a, dcurve=5.0):
    e = np.ones(n); na = max(1, t2s(a))
    if na >= n: return np.linspace(0, 1, n)
    e[:na] = np.linspace(0, 1, na)
    e[na:] = np.exp(-dcurve * np.linspace(0, 1, n - na))
    return e

def env_hold(n, a, r):
    """attack, sustain, release (for pads)."""
    na, nr = max(1, t2s(a)), max(1, t2s(r))
    e = np.ones(n)
    if na + nr >= n:
        return np.hanning(max(3, n))[:n]
    e[:na] = np.linspace(0, 1, na) ** 1.5
    e[-nr:] = np.linspace(1, 0, nr) ** 1.5
    return e

def osc_saw(f, n, det=0.0, vib=0.0, vibhz=5.0):
    t = np.arange(n) / SR
    fa = (np.full(n, f) if np.isscalar(f) else f) * (1 + det)
    if vib: fa = fa * (1 + vib * np.sin(2 * np.pi * vibhz * t))
    ph = np.cumsum(fa) / SR
    return 2 * (ph % 1.0) - 1

def osc_sin(f, n):
    fa = np.full(n, f) if np.isscalar(f) else f
    return np.sin(2 * np.pi * np.cumsum(fa) / SR)

def osc_sq(f, n):
    return np.sign(osc_saw(f, n))

# ---------------- instruments ---------------------------------------------
def kick(vel=1.0, sub=42.0):
    n = t2s(0.30); t = np.arange(n) / SR
    f = 120 * np.exp(-t * 30) + sub
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)
    x += hp(noise(n, 3), 3500) * np.exp(-t * 200) * 0.5
    return x * vel

def snare(vel=1.0):
    n = t2s(0.22); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 195 * t) * np.exp(-t * 32) * 0.5
    nz = hp(noise(n, 7), 1900) * np.exp(-t * 24)
    return (body + nz) * vel * 0.9

def hat(open_=False, vel=1.0):
    n = t2s(0.32 if open_ else 0.05)
    t = np.arange(n) / SR
    return hp(noise(n, 11), 7800) * np.exp(-t * (9 if open_ else 110)) * vel * 0.5

def crash(vel=1.0):
    n = t2s(1.5); t = np.arange(n) / SR
    return hp(noise(n, 13), 3800) * np.exp(-t * 2.6) * vel * 0.7

def timpani(note=41, vel=1.0):
    n = t2s(1.0); t = np.arange(n) / SR
    f0 = midi(note)
    f = f0 * (1 + 0.12 * np.exp(-t * 25))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5.5)
    x += lp(noise(n, 17), 500) * np.exp(-t * 40) * 0.8
    return x * vel

def chug(note, dur, vel=1.0, mute=True):
    """palm-muted power chord (root+5th+octave, drive, dark)."""
    n = t2s(dur); f = midi(note)
    x = sum(osc_saw(f * r, n, det=d) for r in (1, 1.5, 2) for d in (-0.004, 0.004))
    x = np.tanh(x * 1.8)
    x = lp(x, 2400)
    e = env_ad(n, 0.004, 14.0 if mute else 3.0)
    return x * e * vel * 0.5

def bass(note, dur, vel=1.0):
    n = t2s(dur); f = midi(note)
    x = lp(osc_saw(f, n), 850) + 0.6 * osc_sin(f * 0.5, n)
    return x * env_ad(n, 0.006, 6.0) * vel * 0.6

def clav(notes, dur=0.16, vel=1.0):
    n = t2s(dur)
    x = sum(osc_sq(midi(m), n) for m in notes)
    return lp(x, 3800) * env_ad(n, 0.003, 12.0) * vel * 0.22

def stab(notes, dur=0.28, vel=1.0):
    n = t2s(dur)
    x = sum(osc_saw(midi(m), n, det=d) for m in notes for d in (-0.005, 0.005))
    x += 0.5 * sum(osc_sq(midi(m) * 2, n) for m in notes)
    return lp(np.tanh(x * 0.8), 5200) * env_ad(n, 0.008, 7.0) * vel * 0.25

def pad(notes, dur, vel=1.0, bright=1200, att=1.4, rel=2.0):
    n = t2s(dur)
    x = sum(osc_saw(midi(m), n, det=d) for m in notes for d in (-0.004, 0.004))
    return lp(x, bright) * env_hold(n, att, rel) * vel * 0.20

def strings(notes, dur, vel=1.0, bright=1600, att=0.8, rel=1.2):
    n = t2s(dur)
    x = sum(osc_saw(midi(m), n, det=d, vib=0.006, vibhz=5.2)
            for m in notes for d in (-0.006, 0.0, 0.006))
    return lp(x, bright) * env_hold(n, att, rel) * vel * 0.14

def bell(note, dur=2.4, vel=1.0):
    n = t2s(dur); t = np.arange(n) / SR; f = midi(note)
    x = np.zeros(n)
    for i, (r, a) in enumerate(((1, 1), (2.76, 0.4), (5.40, 0.18), (8.93, 0.07))):
        x += a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * (2.5 + i * 3))
    return x * vel * 0.35

def lead(note, dur, vel=1.0, bright=4500):
    n = t2s(dur); f = midi(note)
    x = osc_saw(f, n, det=-0.005) + osc_saw(f, n, det=0.005) + 0.5 * osc_sq(f * 0.5, n)
    return lp(np.tanh(x), bright) * env_ad(n, 0.01, 4.0) * vel * 0.3

# ---------------- mixer -----------------------------------------------------
class Mix:
    def __init__(self, dur):
        self.buf = np.zeros(t2s(dur) + SR)
    def add(self, t, x, gain=1.0):
        i = t2s(t)
        j = min(len(self.buf), i + len(x))
        if j > i: self.buf[i:j] += x[:j - i] * gain
    def master(self, level, clip=0.0, fade_from=None, total=None):
        x = self.buf
        if fade_from is not None:
            i = t2s(fade_from); j = t2s(total)
            x[i:j] *= np.linspace(1, 0, j - i) ** 1.6
            x[j:] = 0
        x /= (np.max(np.abs(x)) + 1e-9)
        if clip > 0:
            x = np.tanh(x * (1 + clip * 3)) / np.tanh(1 + clip * 3)
        return (x * level)[:t2s(total)] if total else x * level

def write_wav(path, x):
    x16 = np.clip(x, -1, 1)
    x16 = (x16 * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(x16.tobytes())

# ============================================================ qa-thrash ====
def make_thrash():
    BPM = 176; b = 60.0 / BPM; bar = 4 * b
    # bars: intro 8, verse 16, chorus 16, verse 16, chorus 16, bridge 8,
    #       chorus 12, outro 2  = 94 bars ~ 128s
    total = 94 * bar + 2
    m = Mix(total)
    E = 40  # E1 midi (root)
    verse_riff  = [0, 0, 3, 0, 5, 0, 3, 2]
    chorus_riff = [12, 12, 15, 12, 17, 15, 12, 10]
    bridge_ch   = [0, 3, 5, 7]

    def drums(bar0, nbars, style):
        for k in range(nbars):
            t0 = (bar0 + k) * bar
            if style == 'intro':
                for i in range(4): m.add(t0 + i * b, kick(0.8))
                for i in range(8): m.add(t0 + i * b / 2, hat(vel=0.5))
            elif style == 'verse':
                pat = [1, 0, 1, 1, 0, 1, 1, 0]
                for i, on in enumerate(pat):
                    if on: m.add(t0 + i * b / 2, kick(0.95))
                m.add(t0 + b, snare(1.0)); m.add(t0 + 3 * b, snare(1.0))
                for i in range(8): m.add(t0 + i * b / 2, hat(vel=0.6))
            elif style == 'chorus':
                for i in range(16): m.add(t0 + i * b / 4, kick(0.8))  # double kick
                m.add(t0 + b, snare(1.05)); m.add(t0 + 3 * b, snare(1.05))
                for i in range(4): m.add(t0 + i * b, hat(open_=True, vel=0.7))
                if k % 4 == 0: m.add(t0, crash(0.9))
            elif style == 'bridge':                       # half-time
                m.add(t0, kick(1.0)); m.add(t0 + 2 * b, snare(1.0))
                m.add(t0 + 3.5 * b, kick(0.7))
                for i in range(4): m.add(t0 + i * b, hat(open_=True, vel=0.5))

    def riff(bar0, nbars, pattern, oct_=0, mute=True):
        for k in range(nbars):
            t0 = (bar0 + k) * bar
            for i, semi in enumerate(pattern):
                m.add(t0 + i * b / 2, chug(E + semi + oct_, b / 2 * 0.9, 0.95, mute))

    B = 0
    drums(B, 8, 'intro'); riff(B, 8, verse_riff); B += 8
    drums(B, 16, 'verse'); riff(B, 16, verse_riff); B += 16
    drums(B, 16, 'chorus'); riff(B, 16, chorus_riff, mute=False); B += 16
    drums(B, 16, 'verse'); riff(B, 16, verse_riff); B += 16
    drums(B, 16, 'chorus'); riff(B, 16, chorus_riff, mute=False); B += 16
    drums(B, 8, 'bridge')
    for k in range(8):
        m.add((B + k) * bar, chug(E + bridge_ch[k % 4], bar * 0.95, 0.9, mute=False))
    B += 8
    drums(B, 12, 'chorus'); riff(B, 12, chorus_riff, mute=False); B += 12
    m.add(B * bar, crash(1.0))
    m.add(B * bar, chug(E, 2.0, 1.0, mute=False))
    return m.master(0.92, clip=0.85, fade_from=total - 2.5, total=total)

# ============================================================ qa-drift =====
def make_drift():
    total = 150.0
    m = Mix(total)
    rng = LCG(777)
    Ab, Fm, Db = [44, 51, 56, 60], [41, 48, 53, 56], [37, 44, 49, 53]
    penta = [68, 70, 72, 75, 77, 80]
    # S1 0-35: single low swelling pad
    for t0 in (0, 12, 24):
        m.add(t0, pad([32, 44, 51], 13, 0.55, bright=650, att=4.5, rel=5))
    # S2 35-72: chord cycle + sparse bells
    t = 35.0; ci = 0
    for t0 in np.arange(35, 72, 12):
        m.add(t0, pad([Ab, Fm, Db][ci % 3], 13, 0.65, bright=900, att=3.5, rel=5)); ci += 1
    while t < 70:
        t += 3.0 + rng.next() * 4.0
        m.add(t, bell(penta[int(rng.next() * 6)], vel=0.5))
    # S3 72-108: brighter, denser bells, soft pulse
    for t0 in np.arange(72, 108, 9):
        ch = [Ab, Fm, Db][ci % 3]; ci += 1
        m.add(t0, pad(ch + [n + 12 for n in ch[1:]], 10, 0.8, bright=1900, att=2.5, rel=4))
    t = 72.0
    while t < 106:
        t += 1.4 + rng.next() * 2.2
        m.add(t, bell(penta[int(rng.next() * 6)] + (12 if rng.next() > 0.6 else 0), vel=0.6))
    for t0 in np.arange(72, 106, 4.0):
        m.add(t0, kick(0.35, sub=36))              # soft heartbeat
    # S4 108-136: thin high shimmer
    for t0 in np.arange(108, 134, 11):
        m.add(t0, pad([75, 80, 84], 12, 0.4, bright=2600, att=4, rel=5))
    t = 108.0
    while t < 132:
        t += 5.0 + rng.next() * 5.0
        m.add(t, bell(penta[int(rng.next() * 6)] + 12, vel=0.35))
    return m.master(0.42, clip=0.0, fade_from=136, total=total)

# ============================================================ qa-funk ======
def make_funk():
    BPM = 104; b = 60.0 / BPM; bar = 4 * b; s16 = b / 4
    # bars: intro 8, A 16, B 16, breakdown 8, B2 10, outro 2 = 60 bars ~139s
    total = 60 * bar + 2
    m = Mix(total)
    G = 31  # G1
    bassline = [31, None, 31, 34, None, 36, 31, None, 38, None, 36, 34, 31, None, 29, None]
    accents  = [1, .4, .6, .4, 1, .4, .7, .5, 1, .4, .6, .4, 1, .5, .8, .5]

    def groove(bar0, nbars, drums=True, clav_on=False, horns=False, open_hats=False):
        for k in range(nbars):
            t0 = (bar0 + k) * bar
            if drums:
                for slot in (0, 7, 10): m.add(t0 + slot * s16, kick(0.95))
                for slot in (4, 12): m.add(t0 + slot * s16, snare(0.9))
                for i in range(16):
                    if open_hats and i == 14: m.add(t0 + i * s16, hat(open_=True, vel=0.6))
                    else: m.add(t0 + i * s16, hat(vel=0.45 * accents[i]))
            for i, note in enumerate(bassline):
                if note is not None:
                    m.add(t0 + i * s16, bass(note, s16 * 1.8, 0.95))
            if clav_on:
                for slot in (2, 6, 11, 14):
                    m.add(t0 + slot * s16, clav([55, 58, 62], vel=0.8))
            if horns and k % 4 == 3:
                for j, ch in enumerate(([55, 58, 62], [57, 60, 64], [58, 62, 65])):
                    m.add(t0 + (13 + j) * s16, stab(ch, vel=0.9))

    B = 0
    groove(B, 8); B += 8
    groove(B, 16, clav_on=True); B += 16
    groove(B, 16, clav_on=True, horns=True, open_hats=True); B += 16
    # breakdown: DRUMS OUT (intensity-jump boundary test)
    for k in range(8):
        t0 = (B + k) * bar
        for i, note in enumerate(bassline):
            if note is not None: m.add(t0 + i * s16, bass(note, s16 * 1.8, 0.8))
        for slot in (2, 11): m.add(t0 + slot * s16, clav([55, 58, 62], vel=0.6))
        if k % 2 == 0: m.add(t0, pad([43, 50, 55, 58], bar * 1.9, 0.5, bright=1100, att=0.8))
    B += 8
    groove(B, 10, clav_on=True, horns=True, open_hats=True); B += 10
    m.add(B * bar, crash(0.8))
    m.add(B * bar, stab([55, 58, 62, 67], 1.2, 1.0))
    m.add(B * bar, bass(31, 2.0, 1.0))
    return m.master(0.78, clip=0.35, fade_from=total - 2.5, total=total)

# ============================================================ qa-crescendo =
def make_crescendo():
    total = 160.0
    m = Mix(total)
    b = 60.0 / 90.0
    Cm, Ab_, Eb, Bb, Gm = [36, 43, 48, 51], [32, 44, 48, 51], [39, 46, 51, 55], [34, 46, 50, 53], [31, 43, 46, 50]
    cello_line = [48, 51, 50, 48, 55, 53, 51, 48]
    # S1 0-30 pp
    for t0 in np.arange(0, 30, 9):
        m.add(t0, strings(Cm, 10.5, 0.12, bright=700, att=2.5, rel=3))
    # S2 30-62 mp: + cello melody, chords move
    prog = [Cm, Ab_, Bb, Gm]
    for i, t0 in enumerate(np.arange(30, 62, 8)):
        m.add(t0, strings(prog[i % 4], 9, 0.20, bright=900, att=2, rel=3))
    for i, t0 in enumerate(np.arange(30, 62, 4)):
        m.add(t0, strings([cello_line[i % 8]], 4.4, 0.25, bright=1300, att=0.5, rel=1.2))
    # S3 62-94 mf: + violins 8va, timpani roll into climax
    for i, t0 in enumerate(np.arange(62, 94, 8)):
        ch = prog[i % 4]
        m.add(t0, strings(ch + [n + 12 for n in ch[1:]], 9, 0.4, bright=1900, att=1.5, rel=2))
    for i, t0 in enumerate(np.arange(62, 94, 4)):
        nte = cello_line[i % 8]
        m.add(t0, strings([nte, nte + 12], 4.4, 0.35, bright=2400, att=0.4, rel=1))
    for i in range(14):                                   # accelerating roll
        m.add(91.0 + i * (3.0 / 14) * (1 - i * 0.02), timpani(36, 0.25 + i * 0.05))
    # S4 94-128 ff CLIMAX — the unambiguous hottest section (boss window)
    clim = [Cm, Ab_, Eb, Bb]
    for i, t0 in enumerate(np.arange(94, 128, 4)):
        ch = clim[i % 4]
        big = ch + [n + 12 for n in ch] + [ch[0] - 12]
        m.add(t0, strings(big, 4.6, 0.95, bright=3400, att=0.15, rel=0.8))
        m.add(t0, stab([n + 12 for n in ch[:3]], 0.5, 1.0))     # brass bite
        m.add(t0, timpani(36, 1.0)); m.add(t0 + 2 * b, timpani(43, 0.85))
        if i % 2 == 0: m.add(t0, crash(0.9))
        m.add(t0 + 2 * b, lead(ch[2] + 24, 1.6, 0.5, bright=5000))
    # S5 128-146 p: solo violin
    solo = [72, 75, 74, 70, 72, 67]
    for i, t0 in enumerate(np.arange(128, 146, 3)):
        m.add(t0, strings([solo[i % 6]], 3.4, 0.14, bright=2000, att=0.6, rel=1.5))
    return m.master(0.95, clip=0.0, fade_from=146, total=total)

# ---------------------------------------------------------------------------
def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else 'tracks'
    os.makedirs(outdir, exist_ok=True)
    for name, fn in (('qa-thrash', make_thrash), ('qa-drift', make_drift),
                     ('qa-funk', make_funk), ('qa-crescendo', make_crescendo)):
        print('rendering', name, '...', flush=True)
        x = fn()
        wav = os.path.join(outdir, name + '.wav')
        mp3 = os.path.join(outdir, name + '.mp3')
        write_wav(wav, x)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav,
                        '-codec:a', 'libmp3lame', '-q:a', '3', mp3], check=True)
        os.remove(wav)
        print('  ->', mp3, f'{len(x)/SR:.1f}s')

if __name__ == '__main__':
    main()
