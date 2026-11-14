# Steaming Ramen — food-picture-01

Entry for make.fun bounty **food-picture-01**,
"Make the best-looking food picture" ($250, 100 paid places).

`main.py` (Python 3.13, standard library only) draws a 1024x1024
picture of one steaming bowl of ramen to
`$MAKEFUN_OUTPUT_DIR/entry.png`: a deep red lacquered bowl of
amber broth on a warm dark wooden table, window light from the
upper left, chopsticks lifting a glossy noodle pull, a halved
soft egg with a jammy orange yolk, seared chashu pork, narutomaki,
green onions and sesame, with thin steam curling up. No text,
no hands, no external assets — every shape, highlight and wisp
of steam is drawn procedurally with scanline fills, gradients
and low-alpha blends.

## How to run

```sh
MAKEFUN_OUTPUT_DIR=out python3 main.py
# writes out/entry.png (1024x1024, < 1 MiB)
```

## Determinism

No clock, no randomness (the one `random.Random` is seeded with
a fixed constant), no network, no timestamps in the output.
Three runs into different directories produce byte-identical
PNGs (verified: same sha256).
