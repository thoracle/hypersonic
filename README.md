# Hypersonic

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
