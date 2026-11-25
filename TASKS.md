# Catalog Future Tasks

Status: `open` | `active` | `done`

## Tasks

| Task | Status | Notes |
| --- | --- | --- |
| Bundle Euclidean `f*`/`g*` motion glyphs into a sprite atlas (`glyphs.webp`) | open | Currently `wp` (3,738 files across 527 entries, 2.22 MB) and `frieze` (570 files across 88 entries, 0.22 MB) store each `f_k`/`g_k` motion glyph as a separate `gen/f<k>.webp` / `gen/g<k>.webp` image. Packing each entry's `2*(N-1)` glyphs into a single `gen/glyphs.webp` sprite in `tools/pack_assets.py` (analogous to `gen/cosets.webp`, referenced via CSS background-position in `tools/make_entry_page.py` / `css/entry.css`) removes **3,693 files**, bringing the 5-family deployed catalog from 21,672 down to **17,979 files** — comfortably under Cloudflare Pages' 20,000-file deployment limit. |
