# Music

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
