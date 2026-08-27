#!/usr/bin/env python3
"""Bundle game.html into a self-contained dist/index.html for a static host.

Produces a page with NO build step and NO server behind it -- suitable for
GitHub Pages (thoracle.github.io/<repo>/). What it does:

  * inlines three.module.js, wrapped in an IIFE so none of its ~1400 top-level
    names can collide with the game's. three.module.js has no top-level
    imports, no import.meta and no dynamic import(), which is what makes that
    safe -- bundle.py re-checks all three and refuses if that ever changes.
  * inlines the Press Start 2P face as a data: URI (the cabinet type is the
    look; a missing font would fall back to system mono).
  * drops the qa-* tones AND the CC-BY reference set from the song list. The
    tones are QA fixtures, not music; the CC-BY tracks are a dev-only A/B
    reference. The shipped songs are ORIGINAL (tools/make_music.py), so the
    built page carries no music licence obligation at all.
  * copies the game tracks to dist/tracks/. They stay FILES rather than data
    URIs: 8MB of audio inside the HTML would have to be base64'd to ~11MB and
    parsed before the page could draw. GitHub Pages serves them with Range
    support, which is what <audio> seeking needs.

The QA POST endpoints need no work here: game.html routes all of them through
qaPost(), which is a no-op off localhost.

"Open file..." in the song picker takes any local audio file, so the page is
still the whole game even where no track is shipped with it.

Usage: tools/bundle.py [--out dist] [--no-tracks]
"""
import argparse, base64, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THREE = 'static/vendor/three.module.js'
FONT = 'static/vendor/PressStart2P-Regular.ttf'


def die(msg):
    print(f'bundle: {msg}', file=sys.stderr)
    sys.exit(1)


def read(rel, binary=False):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p): die(f'missing {rel}')
    return open(p, 'rb').read() if binary else open(p, encoding='utf-8').read()


def once(s, old, new, what):
    n = s.count(old)
    if n != 1: die(f'expected 1 occurrence of {what}, found {n}')
    return s.replace(old, new)


def inline_three(html):
    src = read(THREE)
    # the assumptions that make IIFE-scoping safe
    if re.search(r'^\s*import\s', src, re.M): die('three.module.js has top-level imports')
    if 'import.meta' in src: die('three.module.js uses import.meta')
    if re.search(r'\bimport\s*\(', src): die('three.module.js uses dynamic import()')
    exports = re.findall(r'^export\s*\{', src, re.M)
    if len(exports) != 1: die(f'expected 1 export statement in three, found {len(exports)}')
    # `export { A, B };` -> `return { A, B };`, whole module sealed in an IIFE
    src = re.sub(r'^export\s*\{', 'return {', src, count=1, flags=re.M)
    wrapped = ('/* three.module.js, inlined and IIFE-scoped by tools/bundle.py */\n'
               'const THREE=(()=>{\n' + src + '\n})();\n')
    return once(html, "import * as THREE from './static/vendor/three.module.js';",
                wrapped, 'the three import')


def inline_font(html):
    b64 = base64.b64encode(read(FONT, binary=True)).decode()
    return once(html, "src:url('static/vendor/PressStart2P-Regular.ttf') format('truetype');",
                f"src:url('data:font/ttf;base64,{b64}') format('truetype');",
                'the font url')


def drop_game_tracks(html):
    """--no-tracks ships no audio, so the picker must not offer any -- and the
    CC-BY credit must not name songs that are not there."""
    m = re.search(r"const GAME_TRACKS=\[.*?\];", html, re.S)
    if not m: die('could not find GAME_TRACKS')
    return html.replace(m.group(0), 'const GAME_TRACKS=[];   // --no-tracks')


def drop_ccby_tracks(html):
    """The CC-BY set is a local A/B reference only. Shipping it would put an
    attribution obligation on every fork of the built page; the shipped songs
    are original, so the public build carries no music licence at all."""
    m = re.search(r"const CCBY_TRACKS=\[.*?\];", html, re.S)
    if not m: die('could not find CCBY_TRACKS')
    return html.replace(m.group(0), 'const CCBY_TRACKS=[];   // dev-only reference set')


def drop_qa_tracks(html):
    m = re.search(r"const QA_TRACKS=\[[^\]]*\];", html)
    if not m: die('could not find QA_TRACKS')
    return html.replace(m.group(0), 'const QA_TRACKS=[];   // stripped for distribution')


def game_tracks(html):
    m = re.search(r"const GAME_TRACKS=\[(.*?)\];", html, re.S)
    if not m: die('could not find GAME_TRACKS')
    return re.findall(r"'([^']+)'", m.group(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='dist')
    ap.add_argument('--no-tracks', action='store_true',
                    help='ship index.html alone; players load their own audio')
    a = ap.parse_args()

    html = read('game.html')
    html = inline_font(html)
    html = drop_qa_tracks(html)
    html = drop_ccby_tracks(html)
    tracks = game_tracks(html)
    if a.no_tracks:
        html = drop_game_tracks(html)
    html = inline_three(html)          # last: it makes the file huge to scan

    for stray in re.findall(r'''["'(]/(?:static|tracks)/[^"')]*''', html):
        die(f'absolute asset path survived: {stray}')

    out = os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)
    dest = os.path.join(out, 'index.html')
    open(dest, 'w', encoding='utf-8').write(html)
    total = os.path.getsize(dest)
    print(f'  index.html          {os.path.getsize(dest)/1e6:6.2f} MB')

    if a.no_tracks:
        print('  tracks              skipped (--no-tracks); use "open file..."')
    else:
        tdir = os.path.join(out, 'tracks')
        os.makedirs(tdir, exist_ok=True)
        for t in tracks:
            src = os.path.join(ROOT, 'tracks', t)
            if not os.path.exists(src): die(f'missing track {t}')
            shutil.copy2(src, os.path.join(tdir, t))
            total += os.path.getsize(src)
        print(f'  tracks/             {len(tracks)} files, '
              f'{sum(os.path.getsize(os.path.join(tdir,t)) for t in tracks)/1e6:6.2f} MB')
        # no ATTRIBUTION.md: the shipped music is original. release.py writes
        # a CREDITS.md saying so -- courtesy, not obligation.
    print(f'  total               {total/1e6:6.2f} MB  ->  {a.out}/')


if __name__ == '__main__':
    main()
