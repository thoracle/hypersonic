#!/usr/bin/env python3
"""Assemble the public game repo into release/ — game files only.

This prototype repo holds nine VSPs, telemetry, analysis captures and a
handoff doc, none of which belong in a public release. So the file list here
is an explicit ALLOW-LIST, never a deny-list: a deny-list ships whatever you
forgot to name, and this tree is going to be public.

What lands in release/:

    index.html          the bundled, self-contained game (tools/bundle.py)
    game.html           the readable source it was built from
    static/vendor/      Three.js + the cabinet font, with VERSIONS.md
    tracks/             the five ORIGINAL songs + CREDITS.md
    server.py           local dev server (Range support: <audio> needs it)
    tools/              bundle.py + release.py
    LICENSE             MIT, this project's own code
    THIRD-PARTY.md      what MIT does NOT cover, and why
    licenses/           the verbatim upstream notices those components require
    README.md

Deliberately NOT shipped: the other VSPs (bars, flythrough, heightfield,
landscape, stream, targeting, terrain*, viz2d), runs/, analysis/, RESTART.md,
the qa-* tones, and every QA/analysis tool.

Usage: tools/release.py [--out release] [--force]
"""
import argparse, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    'game.html', 'server.py',
    'LICENSE', 'THIRD-PARTY.md',
    'licenses/three.js-LICENSE.txt', 'licenses/PressStart2P-OFL.txt',
    'static/vendor/three.module.js', 'static/vendor/PressStart2P-Regular.ttf',
    'static/vendor/VERSIONS.md',
    'tools/bundle.py', 'tools/release.py', 'tools/make_music.py',
    'tools/make_qa_tracks.py', 'tools/fingerprint.py',
]

README = """# Hypersonic

**[Play it in your browser →](https://thoracle.github.io/hypersonic/)**

A musical rail shooter. Pick any song and the game listens along and builds the
level out of it: sustained notes raise connected mountain ridges, drum hits
throw up outcrops, quiet passages flood into open sea. There is no authored
content — play the same track twice and you get the same world, play a
different track and you get a different one.

**Play it:** [thoracle.github.io/hypersonic](https://thoracle.github.io/hypersonic/),
or open `index.html` locally. It is one self-contained file — no build step, no
server, no network, nothing to install. Nine songs ship with it, and
**open file…** in the song picker takes any audio file on your machine.

**[Field Manual](https://claude.ai/code/artifact/fedcc5f6-1c07-45f1-bc51-8b8405ae112c)**
— controls, the colour language, the bestiary, scoring.

## Controls

| | |
| --- | --- |
| Move mouse | Aim the reticle. The ship flies itself. |
| Hold click | Sweep-lock every target you pass over — up to eight. |
| Release | Fire the volley. Release *on the beat* to build the rhythm chain. |
| Tap Space | While holding: stack an extra lock on the target under the reticle. |
| E | Overdrive. |
| V | Change view: Retro → wireframe → shaded. |

## Two rules the code enforces structurally

1. **The player always has a valid shot.** A target must never be spawned or
   routed where no honest lock-and-hit window exists. Enforced by spawn proofs,
   a line-of-sight check at every mine drop, and a live cull that unspawns
   anything that sat in weapons range for four seconds while never once being
   targetable.
2. **The ship never crashes into terrain.** Close calls are the point; a
   collision is a bug, not difficulty. A hard floor clamp under the camera and
   the ship ahead makes it impossible, and the water counts as floor.

## Development

    git clone https://github.com/thoracle/hypersonic
    python3 server.py          # localhost:8100, then open /game.html
    python3 tools/bundle.py    # rebuild the self-contained index.html

`server.py` is not `http.server`: it adds HTTP Range support, which `<audio>`
seeking requires, and `Cache-Control: no-store`.

## The music is code too

All five songs are original, written as a program: `tools/make_music.py`
renders them deterministically from a small synthesis toolkit. They are MIT
like everything else here, so nothing in this repo owes anyone attribution.

They were not composed by ear. Each aims at the measured *fingerprint* of a
licensed track it replaced — percussive share, tempo, brightness, dynamic range
— because that fingerprint is exactly what the game reads to pick the biome,
the bestiary and the boss. `tools/fingerprint.py` measures it offline in about
a second, which is what made composing against a target practical.

    python3 tools/make_music.py tracks     # regenerate the songs
    python3 tools/fingerprint.py           # measure what they became

## Licence

MIT (`LICENSE`) — the code, and the music. The bundled Three.js and the Press
Start 2P typeface keep their own licences; see [THIRD-PARTY.md](THIRD-PARTY.md).
"""


CREDITS = """# Music

All nine songs are original to this project and carry no attribution
requirement. They are covered by the same MIT licence as the rest of it
(../LICENSE), and they are made two different ways.

SEVEN ARE WRITTEN AS CODE: `tools/make_music.py` renders them
deterministically from a small synthesis toolkit -- no samples, no model.

TWO ARE GENERATED: `ascend-b` and `neon-alley` come from ACE-Step 1.5, which
is Apache-2.0 and whose output belongs to whoever generated it. They are
re-encoded to match the rest of the set and vetted with the same checker
before shipping.

- neon-run     driving and bright, arpeggio-led
- slow-tide    sustained and tonal; the game floods this one into an archipelago
- ember-drive  drum-led and wide, the most percussive of the set
- gaslight     slow, dark and low-register
- tire-fire    the fastest and brightest
- ghost-light  sparse, tonal and violently dynamic; builds the aurora world
- deep-six     sparse, tonal and even; builds the abyss, and floods it
- ascend-b     generated; driving and wide (ACE-Step)
- neon-alley   generated; the busiest of the set (ACE-Step)

They were chosen against a measured target rather than by ear. The first five
aim at the fingerprint (tools/fingerprint.py) of a licensed track each
replaced, because the fingerprint is what the game reads to choose biome,
bestiary and boss. ghost-light and deep-six aim at a REGION of that
fingerprint instead -- percFrac below 0.03, which no drum-bearing track can
reach -- because that is the only way into the two quiet biomes and the two
bosses that live there. The generated pair were picked by measuring a batch
and playing the survivors.

    python3 tools/make_music.py tracks     # regenerate
    python3 tools/fingerprint.py           # measure what they became
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='release')
    ap.add_argument('--force', action='store_true', help='overwrite an existing tree')
    a = ap.parse_args()
    out = os.path.join(ROOT, a.out)

    if os.path.exists(out):
        if not a.force:
            sys.exit(f'release: {a.out}/ exists — pass --force to replace it')
        shutil.rmtree(out)

    # the bundle is the thing people actually open, so build it fresh
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'bundle.py'),
                    '--out', os.path.join(a.out)], cwd=ROOT, check=True)

    for rel in FILES:
        src = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            sys.exit(f'release: missing {rel}')
        dst = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    open(os.path.join(out, 'tracks', 'CREDITS.md'), 'w').write(CREDITS)
    open(os.path.join(out, 'README.md'), 'w').write(README)
    open(os.path.join(out, '.gitignore'), 'w').write('runs/\nanalysis/\n__pycache__/\n')

    # prove the allow-list held: nothing here may be a VSP or a QA artefact
    banned = ('bars.html', 'flythrough.html', 'heightfield.html', 'landscape.html',
              'stream.html', 'targeting.html', 'terrain.html', 'terrain-scroll.html',
              'viz2d.html', 'RESTART.md', 'analyze_run.py', 'analyze_shots.py',
              'botrun.sh', 'macro_study.py', 'classify_study.py', 'compare_tracks.py')
    # make_qa_tracks.py IS shipped, despite generating fixtures: make_music.py
    # imports its synthesis primitives, so the released tracks cannot be
    # regenerated without it.
    total = 0
    for dirpath, _, names in os.walk(out):
        for nm in names:
            if nm in banned:
                sys.exit(f'release: BANNED file leaked into the tree: {nm}')
            if nm.startswith('qa-'):
                sys.exit(f'release: QA fixture leaked into the tree: {nm}')
            total += os.path.getsize(os.path.join(dirpath, nm))

    n = sum(len(f) for _, _, f in os.walk(out))
    print(f'\nrelease/  {n} files, {total/1e6:.1f} MB — game files only')
    print('  git init && git add . && git commit && push to a public repo')


if __name__ == '__main__':
    main()
