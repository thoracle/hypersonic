# Third-party components

The MIT licence in `LICENSE` covers **this project's own code**. It does not,
and cannot, cover the components below — each keeps its own licence, and each
licence requires that its notice ship with any distribution, including the
bundled `index.html`, which inlines the first two.

| Component | Where | Licence | Notice |
| --- | --- | --- | --- |
| Three.js r170 | `static/vendor/three.module.js` (inlined into `index.html`) | MIT | `licenses/three.js-LICENSE.txt` |
| Press Start 2P | `static/vendor/PressStart2P-Regular.ttf` (inlined into `index.html`) | SIL Open Font License 1.1 | `licenses/PressStart2P-OFL.txt` |
| Four songs by Kevin MacLeod | `tracks/*.mp3` (shipped as files, never inlined) | Creative Commons BY 4.0 | `tracks/CREDITS.md` |


Notes that matter if you fork or re-bundle:

- **The font is OFL, not MIT.** It carries the Reserved Font Name "Press Start
  2P": a modified version may not be distributed under that name. The OFL also
  forbids selling the font on its own — bundled inside software is fine.
- **The music IS third-party, and this reversed once.** Four of the seven
  shipped songs — *Cut and Run*, *Hard Boiled*, *Severe Tire Damage*,
  *Ready Aim Fire* — are by Kevin MacLeod (incompetech.com) under CC BY 4.0.
  The other three — *bright-hook-b*, *cool-b2*, *cool-c-10* — are original
  and MIT. An interim build replaced
  them with original songs from `tools/make_music.py` precisely so that nothing
  here owed attribution; those lost a listening comparison and are now the
  dev-only reference set that `tools/bundle.py` strips. **So a built page DOES
  carry a music licence obligation. Do not re-copy the older claim that it
  does not.**
- **CC BY 4.0 is satisfied by a link, deliberately.** Section 3(a)(1)(D) of the
  licence asks for "a URI or hyperlink to the Public License to the extent
  reasonably practicable", so unlike the two components above there is no
  verbatim text vendored in `licenses/` — the requirement is the *credit*
  travelling with the audio, and that is discharged in three places: the song
  picker in the game, `tracks/CREDITS.md`, and this table. Attribution must
  name the title, the author and the licence, and all three do.
- `tools/bundle.py` inlines Three.js and the font into a single `index.html`.
  That is a distribution of both, so both notices above must ship with it.
