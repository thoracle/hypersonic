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
    tracks/             the five CC-BY songs + ATTRIBUTION.md
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
    'tools/bundle.py', 'tools/release.py',
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
server, no network, nothing to install. Five songs ship with it, and
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

## Licence

This project's own code is MIT (`LICENSE`). The bundled Three.js, the Press
Start 2P typeface and the five music tracks each keep their own licence — see
[THIRD-PARTY.md](THIRD-PARTY.md).
"""


ATTRIBUTION = """# Track attributions

The five tracks in this directory are by Kevin MacLeod (incompetech.com),
licensed under Creative Commons: By Attribution 4.0
(https://creativecommons.org/licenses/by/4.0/):

- heavy-interlude.mp3 ("Heavy Interlude")
- hard-boiled.mp3 ("Hard Boiled")
- severe-tire-damage.mp3 ("Severe Tire Damage")
- cut-and-run.mp3 ("Cut and Run")
- ready-aim-fire.mp3 ("Ready Aim Fire")

CC BY 4.0 requires that this attribution travels with the audio. Keep this file
next to the tracks in any copy, fork or redeployment.

Nothing in this project relicenses them: the MIT grant in ../LICENSE covers the
project's own code only. See ../THIRD-PARTY.md.
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

    # the source ATTRIBUTION.md documents the qa-* fixtures and points at tools
    # this tree does not contain. Ship only the part that is legally required
    # and true of what is actually here.
    open(os.path.join(out, 'tracks', 'ATTRIBUTION.md'), 'w').write(ATTRIBUTION)
    open(os.path.join(out, 'README.md'), 'w').write(README)
    open(os.path.join(out, '.gitignore'), 'w').write('runs/\nanalysis/\n__pycache__/\n')

    # prove the allow-list held: nothing here may be a VSP or a QA artefact
    banned = ('bars.html', 'flythrough.html', 'heightfield.html', 'landscape.html',
              'stream.html', 'targeting.html', 'terrain.html', 'terrain-scroll.html',
              'viz2d.html', 'RESTART.md', 'analyze_run.py', 'analyze_shots.py',
              'botrun.sh', 'macro_study.py', 'classify_study.py', 'compare_tracks.py',
              'make_qa_tracks.py')
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
