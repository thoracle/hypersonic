# Music

All five songs are original to this project, written as code:
`tools/make_music.py` renders them deterministically from a small synthesis
toolkit. They are covered by the same MIT licence as the rest of the project
(../LICENSE) and carry no attribution requirement.

- neon-run     driving and bright, arpeggio-led
- slow-tide    sustained and tonal; the game floods this one into an archipelago
- ember-drive  drum-led and wide, the most percussive of the set
- gaslight     slow, dark and low-register
- tire-fire    the fastest and brightest

They were composed to a measured target rather than by ear: each aims at the
fingerprint (tools/fingerprint.py) of a licensed track it replaced, because the
fingerprint is what the game reads to choose biome, bestiary and boss.

    python3 tools/make_music.py tracks     # regenerate
    python3 tools/fingerprint.py           # measure what they became
