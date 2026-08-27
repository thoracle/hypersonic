#!/usr/bin/env python3
"""Offline replica of game.html's freezeFP() — the 30s track fingerprint.

The fingerprint decides a track's biome, bestiary bias and boss genus, so it is
the thing to aim at when composing music for this game. Measuring it offline
turns a 3-minute bot run into about a second, which is what makes iterating on
generated tracks practical at all.

Mirrors game.html exactly: 48 log bands over 30Hz..12kHz, dB normalised to
(dB+72)/62, adjacency-run flux classification (run >= 5 bands AND the previous
frame's flux over that run < half of this one's = a broadband transient, i.e.
percussion), and the same 10Hz sampling for brightness and dynamic range that
advanceRow() uses.

  percFrac  percussive share of total flux energy   (biome + boss genus)
  tempo     60/median percussive IOI, folded to 0.3..1.0s
  bright    mean normalised spectral centroid       (palette warmth)
  dyn       p90-p10 of the 10Hz mean-band energy    (dynamic range)

Usage: tools/fingerprint.py [track.mp3 ...]     (default: every track in tracks/)
"""
import os, subprocess, sys
import numpy as np

SR, FFT = 48000, 4096
HOP = SR // 60                      # 60Hz analysis frames
BANDS, FMIN, FMAX = 48, 30, 12000
FLOORV, FLUXMIN, PERCRUN = 0.30, 0.055, 5
FP_WINDOW = 30.0                    # the DNA is read once, at 30s

edges = []
_binHz = SR / FFT
for i in range(BANDS + 1):
    f = FMIN * (FMAX / FMIN) ** (i / BANDS)
    b = max(1, min(FFT // 2 - 1, round(f / _binHz)))
    if i > 0:
        b = max(b, edges[i - 1] + 1)
    edges.append(b)


def decode(path):
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le',
                        '-ac', '1', '-ar', str(SR), '-'], capture_output=True)
    if p.returncode:
        raise SystemExit(f'ffmpeg failed on {path}')
    return np.frombuffer(p.stdout, np.float32)


def bands_of(x):
    """Per-frame 48-band normalised levels, as the in-game analyser sees them."""
    win = np.blackman(FFT)
    n = max(0, (len(x) - FFT) // HOP)
    out = np.zeros((n, BANDS))
    for k in range(n):
        seg = x[k * HOP:k * HOP + FFT] * win
        db = 20 * np.log10(np.abs(np.fft.rfft(seg)) / (FFT / 4) + 1e-9)
        for i in range(BANDS):
            out[k, i] = np.clip((db[edges[i]:edges[i + 1]].max() + 72) / 62, 0, 1)
    return out


def fingerprint(path, window=FP_WINDOW):
    vb = bands_of(decode(path))
    nmax = min(len(vb), int(window * 60))
    strAll = strPerc = 0.0
    iois, lastP = [], -9.0
    cenSum = cenN = 0
    eSamp = []
    fluxPrev = np.zeros(BANDS)
    for k in range(nmax):
        t = k / 60.0
        vBand = vb[k]
        vPrev = vb[k - 1] if k else np.zeros(BANDS)
        fluxCur = np.where(vBand >= FLOORV, np.maximum(0, vBand - vPrev), 0)
        b = 0
        while b < BANDS:
            if fluxCur[b] < FLUXMIN:
                b += 1; continue
            b1, s = b, 0.0
            while b1 < BANDS and fluxCur[b1] >= FLUXMIN:
                s += fluxCur[b1]; b1 += 1
            perc = (b1 - b) >= PERCRUN and fluxPrev[b:b1].sum() < s * 0.5
            strAll += s
            if perc:
                strPerc += s
                d = t - lastP
                if 0.15 <= d <= 1.5: iois.append(d)
                if d >= 0.15: lastP = t
            b = b1
        fluxPrev = fluxCur
        if k % 6 == 0:                      # 10Hz, as advanceRow samples
            cw = vBand.sum()
            if cw > 0.5:
                cenSum += float((vBand * np.arange(BANDS)).sum() / cw / BANDS)
                cenN += 1
            eSamp.append(float(vBand.mean()))
    pf = strPerc / strAll if strAll else 0.0
    tempo = 0
    if len(iois) >= 6:
        m = sorted(iois)[len(iois) // 2]
        while m < 0.3: m *= 2
        while m > 1.0: m /= 2
        tempo = round(60 / m)
    es = sorted(eSamp)
    dyn = (es[int(len(es) * 0.9)] - es[int(len(es) * 0.1)]) if es else 0.0
    bright = cenSum / cenN if cenN else 0.5
    fp = {'percFrac': round(pf, 2), 'tempo': tempo,
          'bright': round(bright, 2), 'dyn': round(dyn, 3)}
    # the same thresholds game.html applies in freezeFP()
    fp['biome'] = ('ember' if fp['percFrac'] >= 0.3
                   else ('aurora' if fp['dyn'] >= 0.25 else 'abyss')
                   if fp['percFrac'] < 0.03 else 'veld')
    fp['genus'] = ('carrier' if fp['percFrac'] >= 0.04
                   else 'obelisk' if fp['dyn'] >= 0.25
                   else 'leviathan' if fp['percFrac'] < 0.02 else 'fortress')
    return fp


def main():
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tracks')
    args = sys.argv[1:]
    if not args:
        args = [os.path.join(base, f) for f in sorted(os.listdir(base)) if f.endswith('.mp3')]
    hdr = f"{'track':<24}{'percFrac':>9}{'tempo':>7}{'bright':>8}{'dyn':>8}{'biome':>8}{'genus':>11}"
    print(hdr); print('-' * len(hdr))
    for a in args:
        p = a if os.path.exists(a) else os.path.join(base, a)
        fp = fingerprint(p)
        print(f"{os.path.basename(p)[:-4]:<24}{fp['percFrac']:>9}{fp['tempo']:>7}"
              f"{fp['bright']:>8}{fp['dyn']:>8}{fp['biome']:>8}{fp['genus']:>11}")


if __name__ == '__main__':
    main()
