# Third-party components

The MIT licence in `LICENSE` covers **this project's own code**. It does not,
and cannot, cover the components below — each keeps its own licence, and each
licence requires that its notice ship with any distribution, including the
bundled `index.html`, which inlines the first two.

| Component | Where | Licence | Notice |
| --- | --- | --- | --- |
| Three.js r170 | `static/vendor/three.module.js` (inlined into `index.html`) | MIT | `licenses/three.js-LICENSE.txt` |
| Press Start 2P | `static/vendor/PressStart2P-Regular.ttf` (inlined into `index.html`) | SIL Open Font License 1.1 | `licenses/PressStart2P-OFL.txt` |
| Five music tracks | `tracks/*.mp3` | CC BY 4.0 | `tracks/ATTRIBUTION.md` |

Notes that matter if you fork or re-bundle:

- **The font is OFL, not MIT.** It carries the Reserved Font Name "Press Start
  2P": a modified version may not be distributed under that name. The OFL also
  forbids selling the font on its own — bundled inside software is fine.
- **The tracks are CC BY 4.0** (Kevin MacLeod, incompetech.com). Attribution
  must travel with them; keep `tracks/ATTRIBUTION.md` next to the audio.
  Nothing here relicenses them, and they are not covered by the MIT grant.
- `tools/bundle.py` inlines Three.js and the font into a single `index.html`.
  That is a distribution of both, so both notices above must ship with it.
