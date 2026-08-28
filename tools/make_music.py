#!/usr/bin/env python3
"""Generate five ORIGINAL tracks to replace the CC-BY ones.

Same purpose as make_qa_tracks.py, different goal: those four are deliberately
opposed test fixtures, these five are meant to PLAY like the licensed tracks
they replace, so the public build owes nobody attribution.

The target is each replaced track's offline fingerprint (tools/fingerprint.py),
not its melody. The fingerprint is what the game actually reads -- it picks
biome, bestiary bias and boss genus -- so matching it is what preserves the
gameplay. Aiming in OFFLINE space is deliberate: the offline replica reads
higher than the live analyser (ready-aim-fire is 0.13 offline vs 0.05 in-game),
and targeting like-for-like cancels that offset out.

  neon-run     <- ready-aim-fire      pf 0.13  bright 0.43  dyn 0.16
  slow-tide    <- heavy-interlude     pf 0.09  bright 0.39  dyn 0.10
  ember-drive  <- cut-and-run         pf 0.45  bright 0.34  dyn 0.39
  gaslight     <- hard-boiled         pf 0.16  bright 0.28  dyn 0.16
  tire-fire    <- severe-tire-damage  pf 0.36  bright 0.45  dyn 0.38

THE MACRO CONTOUR IS NOT OPTIONAL. The game ranks a 15s energy envelope
against its own trailing 90s to decide wave size, section archetype and boss
placement. Procedural music is TOO EVEN for that: hold a steady level and the
envelope never moves, the rank sits wherever micro-drift puts it, and the whole
track reads as one long DRIFT section -- tire-fire measured mp p10/p50/p90 of
0/0/0.17 and planned minimum waves for its entire length, 33 spawns against the
531 of the track it replaces. Real music breathes over 20-40s and the rank
follows it (ready-aim-fire reads 0.11/0.9/1.0).

So every track here gets an explicit `contour()`: section-level gain automation
applied BEFORE limiting so the limiter cannot iron it flat. It has to
OSCILLATE, not arc: the rank is taken against a trailing 90s window, so a
single build-to-a-peak leaves everything after the peak ranked below it and the
percentile pinned low for the rest of the track. Alternating verse/chorus
levels every 20-25s is what keeps the rank moving through its range -- which is
exactly what real songs do, and why severe-tire-damage reads 0.05/0.55/0.97
across 22 detected sections. This is the same lesson the terrain macro taught;
see the P1 section of restart.md. The envelope has to keep moving.

MASTERING CUTS BOTH WAYS, and that is the trap. Limiting raises the level a
flat track needs, but it also FLATTENS THE ATTACK EDGES the onset detector
selects on -- and enemy spawns ride those events. Driving tire-fire to clip 1.15
while thinning its kit took it from 77 spawns/min (the track it replaces) to 10.
Match the fingerprint AND the spawn rate, or you have matched the world's look
and lost its gameplay.

MASTERING IS THE BIGGEST LEVER, and it is not obvious. A commercially
mastered track is limited so hard that its band energy sits high and almost
flat -- heavy-interlude reads p10 0.520 / p90 0.620, a spread of one tenth.
An unlimited render of the same arrangement sits at half that level with twice
the spread, so it reads as a quiet, wildly dynamic track no matter what was
played. The `clip` drive in master() is what closes that gap; every value below
was set by measuring, not by ear.

Three more levers, all measured in the FIRST 30 SECONDS, because that is the
window freezeFP() reads:
  percFrac  drum density -- a broadband transient spans >=5 adjacent bands,
            a sustained note does not
  bright    where the energy sits: hats and high leads raise it, sub and
            muted low strings lower it
  dyn       quiet-to-loud CONTRAST INSIDE THE INTRO. A track that opens at a
            steady level reads as low-dynamic no matter what it does at 2:00.

Deterministic (fixed LCG, no wall-clock), pure numpy -> WAV, ffmpeg -> mp3.
Dev tool only; never imported by the game.

  tools/make_music.py [outdir=tracks] [name ...]
"""
import os, subprocess, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_qa_tracks import (SR, Mix, LCG, write_wav, t2s, midi, noise, lp, hp,
                            kick, snare, hat, crash, timpani, chug, bass,
                            clav, stab, pad, strings, bell, lead,
                            osc_sin, env_hold)

# ---------------------------------------------------------------- helpers --
def contour(mix, points, ramp=3.0):
    """Section-level gain automation over the whole buffer.

    `points` is [(seconds, level), ...]; levels are linearly interpolated and
    then smoothed by a `ramp`-second moving average so no edge is a click. Must
    be applied BEFORE master()'s limiter, or the limiter flattens exactly the
    macro movement the game's wave planner reads."""
    n = len(mix.buf)
    ts = np.array([t2s(t) for t, _ in points], dtype=float)
    ls = np.array([l for _, l in points], dtype=float)
    g = np.interp(np.arange(n), ts, ls, left=ls[0], right=ls[-1])
    # box-smooth by cumulative sum, NOT np.convolve: a 3s kernel over a
    # 3-minute buffer is 132k taps x 7.7M samples, which does not finish.
    w = max(1, t2s(ramp) | 1)
    pad = w // 2
    gp = np.concatenate((np.full(pad, g[0]), g, np.full(pad, g[-1])))
    c = np.cumsum(np.insert(gp, 0, 0.0))
    mix.buf *= (c[w:] - c[:-w])[:n] / w
    return mix
def sweep(mix, t0, dur, note=33, vel=0.5):
    """A riser: noise through a rising filter. Tonal-ish, so it lifts bright
    without adding a broadband transient (it has no attack edge)."""
    n = t2s(dur)
    x = noise(n, seed=int(t0 * 7) + 3)
    env = np.linspace(0, 1, n) ** 2
    out = hp(x * env, 400 + 2600 * np.linspace(0, 1, n).mean()) * vel
    mix.add(t0, out)

# -------------------------------------------- voices for the QUIET biomes --
# aurora and abyss both require percFrac < 0.03, and percFrac is the share of
# onset flux that arrives across >=5 ADJACENT bands at once. Every stock
# instrument above fails that somewhere: measured on an identical probe (a
# quiet pad bed plus one voice struck every 1.6s), kick reads 0.174,
# bell(64) 0.141, bass(33) 0.129 and stab 0.098. Two replacements do the same
# musical job under the threshold -- and because percFrac is a RATIO, a track
# that is DENSE in tonal onsets measures LESS percussive than a bare one.

def glass(note, dur=3.2, vel=1.0, att=0.03,
          parts=((1, 1.0), (2.76, 0.30), (5.40, 0.12), (8.93, 0.05))):
    """A struck tone of ISOLATED sine partials over a short attack RAMP.

    This is the voice that makes a sub-0.03 track playable at all: the game
    still spawns enemies on onset events, it just must not class them as
    percussion. Two things do that. Inharmonic sine partials (bell ratios) sit
    further apart than a band is wide, so they light 4 SEPARATED bands instead
    of a run -- unlike a saw or a filtered pluck, whose harmonics fill every
    adjacent band above ~1kHz. And the ramp kills the step splatter of a note
    that begins at full envelope, which is the whole difference from bell():
    same partials, pf 0.023 against 0.107 on the probe.

    Register matters too -- low bands are one FFT bin wide, so the analysis
    window's own main lobe spans five of them. Keep this voice at note >= 60
    and lengthen `att` below that."""
    n = t2s(dur); t = np.arange(n) / SR; f = midi(note)
    x = np.zeros(n)
    for i, (r, a) in enumerate(parts):
        x += a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * (2.2 + i * 2.6))
    na = min(n - 1, max(1, t2s(att)))
    x[:na] *= np.linspace(0, 1, na) ** 2
    return x * vel * 0.35


def softbass(note, dur, vel=1.0, att=0.35):
    """Sub for tracks that may not have a percussive attack anywhere.

    bass() opens in 6ms, and at 40Hz the analyser's own main lobe covers five
    of the one-bin low bands, so a fast low note IS a broadband transient
    (probe: 0.129). Sine plus one octave, opened over a third of a second,
    reads 0.030 for the same note and the same loudness."""
    n = t2s(dur); f = midi(note)
    x = osc_sin(f, n) + 0.35 * osc_sin(f * 2, n)
    return x * env_hold(n, att, min(dur * 0.4, 1.4)) * vel * 0.5


def deepvoice(notes, dur, vel=1.0, bright=900, att=1.8, rel=2.6, harm=7):
    """Sustained LOW chord with no detune and no vibrato.

    pad() and strings() get their warmth by beating two or three saws a few
    cents apart, and strings() adds 5.2Hz vibrato on top. Above a few hundred
    Hz that is inaudible to the classifier, because a band there is dozens of
    FFT bins wide. Below about 175Hz a band is ONE bin, so the same beating
    sweeps energy in and out of single bins and lights a run of adjacent bands
    rising together -- which is the literal definition of the broadband
    transient percFrac counts. Every percussive event in the first draft of
    deep-six fell between 32 and 208Hz and not one of them was a drum
    (percFrac 0.0208 against a <0.02 target, which cost it the leviathan).

    Fixed-frequency partials cannot do that. Movement comes from a sub-Hz
    amplitude LFO instead, which changes level without moving any energy
    between bins."""
    n = t2s(dur); t = np.arange(n) / SR
    x = np.zeros(n)
    for j, mn in enumerate(notes):
        f = midi(mn)
        lfo = 1.0 + 0.10 * np.sin(2 * np.pi * (0.055 + 0.021 * j) * t + j)
        for h in range(1, harm + 1):
            fh = f * h
            if fh > 12000: break
            a = np.exp(-fh / bright) / h
            if a < 0.004: continue
            x += a * np.sin(2 * np.pi * fh * t) * lfo
    return x * env_hold(n, att, rel) * vel * 0.34


def bars(t0, t1, b):
    """Bar start times, in SECONDS, covering [t0, t1).

    Sections are written in seconds throughout this file and bar counts are
    derived. Writing them the other way round is what produced tracks that were
    75s of music in a 176s file: `t = 124 * b` is 124 BEATS, not 124 seconds,
    so every arrangement ended a third of the way in and the rest was silence.
    The game then flew a minute and a half of empty world and held the
    end-of-level mothership until the file ran out."""
    bar = 4 * b
    return [t0 + i * bar for i in range(max(1, int((t1 - t0) / bar)))]


def beat_grid(mix, t0, bars_n, b, pattern, vel=1.0, hats='eighth', ride=False):
    """One drum figure per bar. `pattern` is (kick_beats, snare_beats)."""
    kb, sb = pattern
    for bar_i in range(bars_n):
        bt = t0 + bar_i * 4 * b
        for k in kb: mix.add(bt + k * b, kick(1.0 * vel))
        for s in sb: mix.add(bt + s * b, snare(0.92 * vel))
        if hats == 'eighth':
            for h in range(8): mix.add(bt + h * 0.5 * b, hat(h % 4 == 2, 0.34 * vel))
        elif hats == 'sixteenth':
            for h in range(16): mix.add(bt + h * 0.25 * b, hat(h % 8 == 4, 0.26 * vel))
        elif hats == 'quarter':
            for h in range(4): mix.add(bt + h * b, hat(False, 0.30 * vel))
        if ride and bar_i % 2 == 0: mix.add(bt, crash(0.5 * vel))


# ============================================================== neon-run ===
def make_neon_run():
    """<- ready-aim-fire: driving, BRIGHT, only lightly percussive. The drive
    comes from a sixteenth arpeggio rather than from drums, which is what keeps
    percFrac low while the track still feels fast."""
    BPM = 138; b = 60.0 / BPM; bar = 4 * b
    total = 176.0
    m = Mix(total + 4)
    Em = [52, 55, 59]; C = [48, 52, 55]; G = [50, 55, 62]; D = [50, 54, 57]
    prog = [Em, C, G, D]
    arp_notes = [64, 67, 71, 76, 71, 67]

    def arp(t0, bars_n, ch, vel=0.5, oct_=0):
        for i in range(bars_n * 16):
            t = t0 + i * 0.25 * b
            nt = ch[i % 3] + 12 + oct_ * 12 + (12 if (i // 3) % 2 else 0)
            # soft attack on purpose: a bright plucked attack spans enough
            # adjacent bands to be classified as PERCUSSION, which pushed
            # percFrac to 0.25 against a 0.13 target on the first render
            m.add(t, lead(nt, 0.30, vel * (0.80 + 0.30 * (i % 4 == 0)), bright=3600))

    # 0-16s INTRO: arpeggio alone, rising -- quiet start gives dyn its floor
    for i, t0 in enumerate(bars(0, 16, b)):
        arp(t0, 4, prog[i % 4], 0.46 + i * 0.02)
        m.add(t0, pad([n - 12 for n in prog[i % 4]], 4 * b, 0.46, bright=2600))
        m.add(t0, bass(prog[i % 4][0] - 24, 4 * b, 0.42))
    # 16-32s: drums in, but sparse -- backbeat only, keeping percFrac down
    for i, t0 in enumerate(bars(16, 32, b)):
        arp(t0, 4, prog[i % 4], 0.42)
        beat_grid(m, t0, 4, b, ([0], [2]), 0.62, hats='quarter')
        m.add(t0, pad([n - 12 for n in prog[i % 4]], 4 * b, 0.30, bright=3000))
        m.add(t0, bass(prog[i % 4][0] - 24, 4 * b, 0.55))
    # 32-64s VERSE
    for i, t0 in enumerate(bars(32, 64, b)):
        ch = prog[i % 4]
        arp(t0, 4, ch, 0.56)
        arp(t0 + 0.125 * b, 4, ch, 0.30, oct_=1)
        beat_grid(m, t0, 4, b, ([0, 2.5], [2]), 0.72, hats='quarter')
        m.add(t0, bass(ch[0] - 24, 4 * b, 0.62))
        m.add(t0, pad([n - 12 for n in ch], 4 * b, 0.26, bright=3200))
        if i % 4 == 2: m.add(t0, lead(ch[2] + 12, 2 * b, 0.34, bright=6000))
    # 64-104s CHORUS: the hottest stretch -- boss window
    for i, t0 in enumerate(bars(64, 104, b)):
        ch = prog[i % 4]
        arp(t0, 4, ch, 0.70, oct_=1)
        arp(t0 + 0.125 * b, 4, ch, 0.38)
        beat_grid(m, t0, 4, b, ([0, 2.5], [2]), 0.86, hats='quarter', ride=False)
        m.add(t0, bass(ch[0] - 24, 4 * b, 0.8))
        m.add(t0, strings([n + 12 for n in ch], 4 * b, 0.34, bright=4200, att=0.05))
        m.add(t0 + 2 * b, lead(ch[1] + 24, 1.6 * b, 0.44, bright=6500))
    # 104-124s BRIDGE: drums out, pads only -- the breather
    for i, t0 in enumerate(bars(104, 124, b)):
        ch = prog[(i + 2) % 4]
        m.add(t0, pad([n for n in ch] + [ch[0] + 12], 4.4 * b, 0.42, bright=3000, att=0.9))
        m.add(t0 + 2 * b, bell(ch[2] + 24, 2.2, 0.30))
    sweep(m, 122.0, 2 * b, vel=0.35)
    # 124-168s FINAL CHORUS
    for i, t0 in enumerate(bars(124, total - 8, b)):
        ch = prog[i % 4]
        arp(t0, 4, ch, 0.72, oct_=1)
        arp(t0 + 0.125 * b, 4, ch, 0.40)
        beat_grid(m, t0, 4, b, ([0, 2.5], [2]), 0.86, hats='quarter', ride=False)
        m.add(t0, bass(ch[0] - 24, 4 * b, 0.85))
        m.add(t0, strings([n + 12 for n in ch], 4 * b, 0.38, bright=4600, att=0.05))
    contour(m, [(0, 0.42), (14, 0.62), (26, 0.95), (40, 0.58), (54, 1.00),
                (68, 0.62), (82, 1.00), (96, 0.55), (110, 0.34), (124, 0.90),
                (138, 0.56), (152, 1.00), (total, 0.80)])
    return m.master(0.95, clip=0.42, fade_from=total - 8, total=total)


# ============================================================= slow-tide ===
def make_slow_tide():
    """<- heavy-interlude: sustained and tonal, almost no percussion, and
    deliberately EVEN in level -- the low dynamic range is the point, so the
    intro opens at close to the track's average."""
    BPM = 96; b = 60.0 / BPM
    total = 168.0
    m = Mix(total + 4)
    Am = [57, 60, 64]; F = [53, 57, 60]; C = [48, 52, 55]; G = [55, 59, 62]
    prog = [Am, F, C, G]
    # a continuous drone under everything: the dips between phrases were what
    # made a deliberately EVEN track measure as dynamic (0.267 against 0.101)
    for i in range(int(total / 8) + 1):
        m.add(i * 8.0, pad([45, 57], 8.6, 0.52, bright=1300, att=2.0, rel=2.5))
    for i in range(int(total / (8 * b))):
        t0 = i * 8 * b
        ch = prog[i % 4]
        if t0 > total - 10: break
        # the bed: wide sustained strings, always present -> flat dynamics
        m.add(t0, strings(ch + [ch[0] - 12], 8.4 * b, 0.55, bright=2600, att=1.2, rel=2.2))
        m.add(t0, pad([n + 12 for n in ch], 8.4 * b, 0.30, bright=2400, att=1.6, rel=2.4))
        # a bell melody carries the brightness without adding transients
        if i % 2 == 0:
            m.add(t0 + 2 * b, bell(ch[2] + 12, 3.0, 0.22))
            m.add(t0 + 5 * b, bell(ch[1] + 12, 2.4, 0.18))
        # the barest pulse: a soft kick on 1, a hat on 3. Nothing broadband.
        m.add(t0, kick(0.34))
        m.add(t0 + 4 * b, hat(False, 0.20))
        if 56 * b < t0 < 112 * b:          # the swell that owns the boss window
            m.add(t0, strings([n + 12 for n in ch], 8.4 * b, 0.40, bright=3800, att=0.6))
            m.add(t0 + 4 * b, bell(ch[0] + 24, 2.6, 0.30))
            m.add(t0, kick(0.42)); m.add(t0 + 2 * b, snare(0.30))
    # even slow-tide has to breathe -- shallower than the rest, but present
    contour(m, [(0, 0.62), (18, 0.86), (34, 0.60), (52, 0.95), (70, 0.64),
                (88, 1.00), (106, 0.62), (124, 0.88), (142, 0.66), (total, 0.80)],
            ramp=5.0)
    return m.master(0.92, clip=1.20, fade_from=total - 12, total=total)


# =========================================================== ember-drive ===
def make_ember_drive():
    """<- cut-and-run: drum-led and WIDE. The dynamic range has to live inside
    the first 30s, so it opens on a bare floor tom figure and slams into a full
    kit at 0:16 -- that contrast IS the dyn number."""
    BPM = 108; b = 60.0 / BPM
    total = 172.0
    m = Mix(total + 4)
    Dm = [50, 53, 57]; Bb = [46, 50, 53]; F = [53, 57, 60]; C = [48, 52, 55]
    prog = [Dm, Bb, F, C]
    # 0-16s: sparse toms, quiet -- the floor of the dynamic range
    for i, t0 in enumerate(np.arange(0, 16, 2 * b)):
        m.add(t0, timpani(38, 0.34)); m.add(t0 + 1.5 * b, timpani(45, 0.22))
        m.add(t0, bass(38 - 12, 2 * b, 0.30))
    sweep(m, 14.0, 2 * b, vel=0.5)
    # 16-64s: the full kit -- the ceiling
    for i, t0 in enumerate(bars(16, 64, b)):
        ch = prog[i % 4]
        beat_grid(m, t0, 4, b, ([0, 1.5, 2.75], [1, 3]), 1.0, hats='sixteenth', ride=True)
        m.add(t0, bass(ch[0] - 12, 4 * b, 0.85))
        m.add(t0, chug(ch[0] - 12, 4 * b, 0.5))
        if i % 2 == 0: m.add(t0, stab(ch, 0.4, 0.55))
    # 64-104s: the hottest section
    for i, t0 in enumerate(bars(64, 104, b)):
        ch = prog[i % 4]
        beat_grid(m, t0, 4, b, ([0, 1.5, 2.5, 3.5], [1, 3]), 1.0, hats='sixteenth', ride=True)
        m.add(t0, bass(ch[0] - 12, 4 * b, 0.95))
        m.add(t0, chug(ch[0] - 12, 4 * b, 0.72))
        m.add(t0, stab([n + 12 for n in ch], 0.36, 0.7))
        m.add(t0 + 2 * b, stab(ch, 0.3, 0.55))
        if i % 4 == 0: m.add(t0, crash(0.85))
    # 104-124s: breakdown, drums out
    for i, t0 in enumerate(bars(104, 124, b)):
        ch = prog[(i + 1) % 4]
        m.add(t0, pad(ch, 4.4 * b, 0.45, bright=2200, att=0.8))
        m.add(t0 + 2 * b, timpani(38, 0.45))
    # 124-end: return
    for i, t0 in enumerate(bars(124, total - 8, b)):
        ch = prog[i % 4]
        beat_grid(m, t0, 4, b, ([0, 1.5, 2.5, 3.5], [1, 3]), 1.0, hats='sixteenth', ride=True)
        m.add(t0, bass(ch[0] - 12, 4 * b, 0.95))
        m.add(t0, chug(ch[0] - 12, 4 * b, 0.75))
    contour(m, [(0, 0.30), (14, 0.52), (26, 0.95), (40, 0.60), (54, 1.00),
                (68, 0.58), (82, 1.00), (96, 0.62), (110, 0.30), (124, 0.92),
                (138, 0.58), (152, 1.00), (total, 0.82)])
    return m.master(0.95, clip=0.35, fade_from=total - 8, total=total)


# =============================================================== gaslight ===
def make_gaslight():
    """<- hard-boiled: slow, DARK, low-register. Brightness is the target to
    miss downward here -- closed hats only, muted low chords, no cymbals."""
    BPM = 88; b = 60.0 / BPM
    total = 170.0
    m = Mix(total + 4)
    Cm = [48, 51, 55]; Ab = [44, 48, 51]; Fm = [53, 56, 60]; G7 = [55, 59, 62]
    prog = [Cm, Ab, Fm, G7]
    for i, t0 in enumerate(bars(0, total - 2, b)):
        ch = prog[i % 4]
        hot = 60 * b < t0 < 116 * b       # the boss window
        m.add(t0, bass(ch[0] - 24, 4 * b, 0.75 if hot else 0.6))
        m.add(t0 + 2.5 * b, bass(ch[1] - 24, 1.4 * b, 0.42))
        # brushed kit: kick + rim, closed hats, nothing above ~5k
        m.add(t0, kick(0.8 if hot else 0.62))
        m.add(t0 + 2 * b, snare(0.5 if hot else 0.36))
        for h in range(4): m.add(t0 + h * b, hat(False, 0.13))
        if hot: m.add(t0 + 3.5 * b, kick(0.5))
        # dark low chords, no upper extensions
        m.add(t0, pad([n - 12 for n in ch], 4.2 * b, 0.52, bright=850, att=0.5))
        if i % 2 == 0:
            m.add(t0 + 1 * b, clav([ch[1], ch[2]], 0.22, 0.26))
        if hot and i % 2 == 1:
            m.add(t0 + 2 * b, lead(ch[2] + 12, 1.4 * b, 0.24, bright=2600))
    contour(m, [(0, 0.54), (20, 0.86), (36, 0.56), (52, 1.00), (68, 0.58),
                (84, 0.94), (100, 0.60), (116, 1.00), (132, 0.54), (148, 0.90),
                (total, 0.70)], ramp=4.0)
    return m.master(0.92, clip=0.90, fade_from=total - 10, total=total)


# ============================================================== tire-fire ===
def make_tire_fire():
    """<- severe-tire-damage: fast, bright AND percussive, with real dynamics.
    The brightest of the five -- open hats, crashes and a high lead."""
    BPM = 146; b = 60.0 / BPM
    total = 168.0
    m = Mix(total + 4)
    Am = [57, 60, 64]; G = [55, 59, 62]; F = [53, 57, 60]; E = [52, 56, 59]
    prog = [Am, G, F, E]
    # 0-12s: hats and a lead over a sustained bed. The bed matters -- the first
    # render opened on hats alone and measured p10 0.015, near silence, which
    # alone doubled the dynamic range the fingerprint saw.
    for i, t0 in enumerate(np.arange(0, 12, 0.5 * b)):
        m.add(t0, hat(i % 4 == 2, 0.34))
    for t0 in bars(0, 12, b):
        m.add(t0, pad([57, 64, 69], 4.4 * b, 0.55, bright=3200, att=0.4))
        m.add(t0, bass(33, 4 * b, 0.55))
    for i, t0 in enumerate(np.arange(0, 12, 3 * b)):
        m.add(t0, lead(76 + (i % 2) * 4, 2.4 * b, 0.38, bright=6500))
    sweep(m, 10.0, 2 * b, vel=0.55)
    # 12-56s: full speed
    for i, t0 in enumerate(bars(12, 56, b)):
        ch = prog[i % 4]
        beat_grid(m, t0, 4, b, ([0, 2], [1, 3]), 1.0, hats='sixteenth', ride=True)
        m.add(t0, bass(ch[0] - 24, 4 * b, 0.8))
        m.add(t0, chug(ch[0] - 12, 4 * b, 0.45))
        m.add(t0 + 2 * b, lead(ch[2] + 12, 1.6 * b, 0.42, bright=6800))
    # 56-104s: the hottest section
    for i, t0 in enumerate(bars(56, 104, b)):
        ch = prog[i % 4]
        beat_grid(m, t0, 4, b, ([0, 2], [1, 3]), 1.0, hats='sixteenth', ride=True)
        m.add(t0, bass(ch[0] - 24, 4 * b, 0.95))
        m.add(t0, chug(ch[0] - 12, 4 * b, 0.6))
        m.add(t0, stab([n + 12 for n in ch], 0.3, 0.6))
        m.add(t0 + 2 * b, lead(ch[2] + 24, 1.4 * b, 0.5, bright=7200))
        if i % 2 == 0: m.add(t0, crash(0.75))
    # 104-120s: half-time breather
    for i, t0 in enumerate(bars(104, 120, b)):
        ch = prog[(i + 2) % 4]
        m.add(t0, pad([n + 12 for n in ch], 4.4 * b, 0.40, bright=3600, att=0.6))
        m.add(t0, kick(0.6)); m.add(t0 + 2 * b, snare(0.5))
        for h in range(4): m.add(t0 + h * b, hat(h == 2, 0.26))
    # 120-end
    for i, t0 in enumerate(bars(120, total - 8, b)):
        ch = prog[i % 4]
        beat_grid(m, t0, 4, b, ([0, 2], [1, 3]), 1.0, hats='sixteenth', ride=True)
        m.add(t0, bass(ch[0] - 24, 4 * b, 0.95))
        m.add(t0 + 2 * b, lead(ch[2] + 24, 1.4 * b, 0.5, bright=7200))
        if i % 2 == 0: m.add(t0, crash(0.75))
    contour(m, [(0, 0.44), (12, 0.66), (24, 0.96), (38, 0.60), (50, 1.00),
                (64, 0.62), (78, 1.00), (92, 0.58), (106, 0.34), (118, 0.94),
                (132, 0.60), (146, 1.00), (total, 0.84)])
    return m.master(0.95, clip=0.38, fade_from=total - 8, total=total)


# ============================================================= ghost-light ==
def make_ghost_light():
    """AURORA / obelisk -- the first track that opens the quiet biomes.

    The whole shipped set is veld or ember, because the fingerprint sends a
    track to aurora only at percFrac < 0.03 AND dyn >= 0.25: sparse, tonal,
    NO drums, and yet violently dynamic inside the first 30 seconds. Those two
    pull against each other -- the obvious way to get a wide dynamic range is
    to hit something -- so the range here is built out of PRESENCE instead of
    impact: the track alternates between a single high drone (two bands lit out
    of forty-eight) and a full-register curtain (all of them), which is a
    far bigger swing in mean band energy than any drum kit produces.

    That alternation is also rule 2, on a ~22s cycle, so the same structure
    that earns the biome keeps the wave planner moving. Nothing here is
    percussive, so tempo reads 0 and the whole track classes as DRIFT -- which
    is exactly the condition the obelisk needs.

    Two things are deliberately NOT done. No bells (they read percussive; see
    glass()), and no limiter drive above ~0.5, because tanh drive lifts the
    thin passages far more than the loud ones and dyn is the number it eats
    first."""
    total = 172.0
    m = Mix(total + 6)
    rng = LCG(1907)
    Am = [57, 60, 64]; F = [53, 57, 60]; C = [48, 52, 55]; Em = [52, 55, 59]
    prog = [Am, F, C, Em]
    penta = [69, 72, 74, 76, 79, 81, 84]

    def veil(t0, dur, vel=0.5):
        """The thin state. Two high notes and nothing else -- almost the whole
        spectrum sits under the analyser floor, which is where dyn's p10 comes
        from. A wider or lower 'quiet' passage still lights thirty bands and
        the dynamic range collapses."""
        m.add(t0, pad([81, 88], dur + 1.2, vel, bright=3400, att=2.0, rel=2.6))

    def curtain(t0, dur, ch, vel=1.0, bright=2600, low=True, top=True):
        m.add(t0, strings(ch + [n + 12 for n in ch], dur + 1.4,
                          0.62 * vel, bright=bright, att=1.5, rel=2.4))
        if top:
            m.add(t0, pad([n + 24 for n in ch], dur + 1.2,
                          0.42 * vel, bright=bright + 1600, att=2.2, rel=2.6))
        if low:
            m.add(t0, pad([n - 12 for n in ch], dur + 1.2,
                          0.50 * vel, bright=1200, att=1.8, rel=2.4))
            m.add(t0, softbass(ch[0] - 24, dur + 0.8, 0.60 * vel))

    def glints(t0, t1, lo=1.4, hi=3.0, vel=0.55, oct_=0):
        """The onset stream. Enemies ride these, so density here is the level's
        population -- and every one of them also DILUTES percFrac, which is a
        ratio, so a busy sky is cheaper than an empty one."""
        t = t0
        while t < t1:
            n = penta[int(rng.next() * len(penta))] + oct_ * 12
            m.add(t, glass(n, 3.4, vel * (0.7 + 0.5 * rng.next())))
            t += lo + rng.next() * (hi - lo)

    # 0-9   the veil: nothing but the high drone. dyn's floor lives here.
    veil(0, 9, 0.42)
    glints(2.5, 8.5, 2.4, 4.0, 0.30, oct_=0)
    # 9-26  first curtain, opening wide
    curtain(9, 17, Am, 0.85)
    glints(9, 26, 1.5, 2.8, 0.55)
    # 26-33 collapse -- the second thin window the p10 needs
    veil(26, 7, 0.40)
    glints(27, 32, 2.2, 3.6, 0.32)
    # 33-56 second curtain, brighter and taller
    for i, t0 in enumerate((33, 44)):
        curtain(t0, 11, prog[i % 4], 1.0, bright=3000)
    glints(33, 56, 1.2, 2.4, 0.65, oct_=0)
    # 56-64 thin
    veil(56, 8, 0.44)
    glints(57, 63, 2.4, 4.2, 0.34)
    # 64-100 THE CORONA: the hottest stretch, so the boss window
    for i, t0 in enumerate((64, 76, 88)):
        curtain(t0, 12, prog[(i + 1) % 4], 1.0, bright=3600)
        m.add(t0, strings([n + 24 for n in prog[(i + 1) % 4]], 13,
                          0.34, bright=5200, att=1.2, rel=2.0))
    glints(64, 100, 1.0, 2.0, 0.72, oct_=0)
    glints(70, 100, 2.0, 3.4, 0.40, oct_=1)
    # 100-110 thin
    veil(100, 10, 0.46)
    glints(101, 109, 2.6, 4.4, 0.34)
    # 110-136 third curtain
    for i, t0 in enumerate((110, 123)):
        curtain(t0, 13, prog[(i + 2) % 4], 0.92, bright=2800)
    glints(110, 136, 1.3, 2.6, 0.62)
    # 136-144 thin
    veil(136, 8, 0.44)
    glints(137, 143, 2.4, 4.0, 0.32)
    # 144-172 final curtain, resolving back onto the drone
    curtain(144, 14, Am, 1.0, bright=3400)
    curtain(158, 10, F, 0.80, bright=2600, top=False)
    glints(144, 166, 1.2, 2.4, 0.68)
    veil(160, 12, 0.40)
    contour(m, [(0, 0.30), (9, 0.86), (20, 1.00), (30, 0.34), (40, 0.92),
                (50, 1.00), (60, 0.36), (72, 0.96), (84, 1.00), (96, 0.40),
                (106, 0.34), (118, 0.92), (130, 0.98), (140, 0.36),
                (150, 1.00), (162, 0.86), (total, 0.60)], ramp=4.0)
    return m.master(0.95, clip=0.42, fade_from=total - 10, total=total)


# =============================================================== deep-six ===
def make_deep_six():
    """ABYSS / leviathan -- the other world nobody has seen.

    Same percFrac < 0.03, opposite dynamic requirement: dyn must stay UNDER
    0.25, and percFrac under 0.02 as well, which is what separates the
    leviathan from the fortress. So where ghost-light spends its first 30
    seconds swinging between two bands lit and forty-eight, this one holds a
    continuous sub drone under everything from sample zero -- the same trick
    slow-tide needed when its inter-phrase dips made a deliberately even track
    measure as dynamic (0.267 against a 0.101 target).

    But the wave planner still reads the whole track, and rule 2 is not
    optional. So the CONTOUR is deliberately two-part: gentle inside the
    fingerprint's 30s window (0.66 to 0.82, about 2dB, which dyn barely sees)
    and then swinging its full range for the remaining two and a half minutes.
    Narrow fingerprint, wide level. Those are measured over different windows
    and there is no reason to trade one for the other.

    The limiter is driven hard here (unlike ghost-light) for the opposite
    reason: nothing in this track has an attack edge to flatten, and without
    the drive a track this sustained reads under the 0.18 level floor and the
    onset flux stops clearing its threshold."""
    total = 176.0
    m = Mix(total + 6)
    rng = LCG(4460)
    Dm = [50, 53, 57]; Bb = [46, 50, 53]; Gm = [43, 46, 50]; Am = [45, 48, 52]
    prog = [Dm, Bb, Gm, Am]
    tones = [62, 65, 67, 69, 72, 74, 77]

    # The floor: an unbroken sub drone, overlapping so it never re-attacks.
    # This is the single reason dyn stays narrow -- remove it and the gaps
    # between chords become the dynamic range. deepvoice, not pad: everything
    # under ~175Hz here has to be beat-free or it reads as percussion.
    for i in range(int(total / 9) + 2):
        m.add(i * 9.0, deepvoice([26, 38], 9.8, 0.72, bright=430, att=3.0, rel=3.4))
        m.add(i * 9.0, softbass(26, 9.6, 0.30, att=1.6))

    def bed(t0, dur, ch, vel=1.0, bright=1300, high=False):
        # the body sits ON the chord and above it; the saw-based voices never
        # go below it, and the octaves underneath are deepvoice
        m.add(t0, deepvoice([ch[0] - 24, ch[0] - 12, ch[1] - 12], dur + 1.2,
                            0.62 * vel, bright=620, att=2.2, rel=2.8))
        m.add(t0, strings(ch + [n + 12 for n in ch], dur + 1.4,
                          0.46 * vel, bright=bright, att=1.8, rel=2.6))
        if high:
            m.add(t0, pad([n + 12 for n in ch], dur + 1.0,
                          0.30 * vel, bright=bright + 900, att=2.6, rel=3.0))

    def calls(t0, t1, lo=2.0, hi=4.0, vel=0.45, oct_=0):
        t = t0
        while t < t1:
            n = tones[int(rng.next() * len(tones))] + oct_ * 12
            m.add(t, glass(n, 4.0, vel * (0.7 + 0.5 * rng.next()), att=0.05))
            t += lo + rng.next() * (hi - lo)

    # 0-34 THE FINGERPRINT WINDOW: held flat on purpose. One chord change,
    # no register jumps, sparse calls -- everything that would widen dyn.
    bed(0, 17, Dm, 0.90)
    bed(17, 17, Bb, 0.94)
    calls(3, 34, 2.6, 4.4, 0.42)
    # 34-70 the shelf drops away: the level starts moving
    for i, t0 in enumerate((34, 46, 58)):
        bed(t0, 12, prog[i % 4], 1.0, bright=1500, high=(i == 2))
    calls(34, 70, 1.8, 3.2, 0.52)
    # 70-84 a trough -- almost only the drone
    calls(70, 84, 3.4, 5.6, 0.34)
    # 84-124 THE DEEP: hottest, sustained and tonal, which is the DRIFT
    # section the leviathan needs to be given a window at all
    for i, t0 in enumerate((84, 96, 108)):
        bed(t0, 13, prog[(i + 1) % 4], 1.0, bright=1900, high=True)
        m.add(t0, strings([n + 12 for n in prog[(i + 1) % 4]], 14,
                          0.30, bright=2800, att=1.4, rel=2.2))
    calls(84, 124, 1.4, 2.6, 0.60)
    calls(90, 124, 2.6, 4.2, 0.34, oct_=1)
    # 124-138 second trough
    calls(124, 138, 3.2, 5.4, 0.34)
    # 138-176 the surface: last swell, then the drone alone
    for i, t0 in enumerate((138, 152)):
        bed(t0, 14, prog[(i + 2) % 4], 0.94, bright=1700, high=(i == 0))
    calls(138, 166, 1.8, 3.2, 0.54)
    # Troughs are PLATEAUS, not notches. The macro rank is a percentile against
    # a trailing 90s, i.e. a trend detector, so a level that only dips briefly
    # ranks near the ceiling almost all the time -- the first draft measured a
    # macro median of 0.94 against a 0.92 limit. Time spent low is what moves
    # the median; the depth of a notch does not.
    contour(m, [(0, 0.70), (12, 0.80), (24, 0.76), (32, 0.60), (40, 0.38),
                (50, 0.36), (58, 0.95), (68, 1.00), (76, 0.42), (86, 0.38),
                (94, 1.00), (104, 0.96), (112, 0.42), (122, 0.38),
                (130, 0.98), (140, 1.00), (148, 0.44), (156, 0.42),
                (164, 0.90), (total, 0.70)], ramp=5.0)
    return m.master(0.93, clip=1.05, fade_from=total - 12, total=total)


TRACKS = (('neon-run', make_neon_run), ('slow-tide', make_slow_tide),
          ('ember-drive', make_ember_drive), ('gaslight', make_gaslight),
          ('tire-fire', make_tire_fire), ('ghost-light', make_ghost_light),
          ('deep-six', make_deep_six))


def main():
    args = sys.argv[1:]
    outdir = args[0] if args and not args[0].endswith('.py') else 'tracks'
    want = set(args[1:]) if len(args) > 1 else None
    os.makedirs(outdir, exist_ok=True)
    for name, fn in TRACKS:
        if want and name not in want: continue
        print('rendering', name, '...', flush=True)
        x = fn()
        # A track that stops early and pads with silence is the failure mode
        # this file already shipped once: the game keeps flying an empty world
        # and holds the end-of-level mothership until the FILE runs out, so the
        # player sits through a minute of silence waiting to be picked up.
        # Fail the render rather than let it reach a track list again.
        env = np.maximum.reduceat(np.abs(x), np.arange(0, len(x) - 4800, 4800))
        live = np.where(env > 0.002)[0]
        tail = (len(x) / SR) - (live[-1] * 4800 / SR if len(live) else 0)
        if tail > 4.0:
            raise SystemExit(f'{name}: {tail:.1f}s of trailing silence '
                             f'(music ends at {live[-1] * 4800 / SR:.1f}s of '
                             f'{len(x)/SR:.1f}s) -- sections are mistimed')
        wav = os.path.join(outdir, name + '.wav')
        mp3 = os.path.join(outdir, name + '.mp3')
        write_wav(wav, x)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav,
                        '-codec:a', 'libmp3lame', '-q:a', '3', mp3], check=True)
        os.remove(wav)
        print('  ->', mp3, f'{len(x)/SR:.1f}s')


if __name__ == '__main__':
    main()
