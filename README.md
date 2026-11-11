# Quote Sources

This repository stores quote datasets and related images, grouped by source.
It is the source of truth for quote text; consumers should load the JSON data
directly instead of generating or baking quote lists into templates.

## Layout

```text
sources/
└── disco-elysium/
	├── images/                 # Source-specific portraits and artwork
	├── quotes/
	│   ├── quotes.json         # Canonical quote collection
	│   └── speakers.json       # Speaker names and image paths
	└── templates/              # Layouts that render a selected quote

helpers/                        # Optional curation and image-processing tools
├── data/                       # Local pipeline inputs/outputs
└── portraits_raw/              # Original inputs for image processing
```

Each new quote collection gets its own directory under `sources/`, with its
own `quotes/` and `images/` directories (for example `max-payne/`). Keep
source-specific data together; do not add another source's quotes or artwork
to the Disco Elysium files. Add a source-specific `templates/` directory when
that collection needs its own TRMNL layouts; layouts do not need to be generic
across different sources.

## Loading quotes

The canonical Disco Elysium collection is
[`sources/disco-elysium/quotes/quotes.json`](sources/disco-elysium/quotes/quotes.json).
It has a top-level `quotes` array. Read that JSON at runtime and choose a quote
from the array; do not copy it into generated Liquid templates. The current
raw JSON URL is:

`https://raw.githubusercontent.com/Kaskelotval/trmnl-quotes/main/sources/disco-elysium/quotes/quotes.json`

For example, a consumer can fetch the live collection and select a quote like
this:

```js
const response = await fetch(
	"https://raw.githubusercontent.com/Kaskelotval/trmnl-quotes/main/sources/disco-elysium/quotes/quotes.json",
);
const { quotes } = await response.json();
const quote = quotes[Math.floor(Math.random() * quotes.length)];
```

Alternatively, bundle/import the JSON file in the consuming application.

## Templates

The Disco Elysium layouts are in
[`sources/disco-elysium/templates/`](sources/disco-elysium/templates/). They
use two TRMNL Polling responses: `IDX_0` for the quote collection and `IDX_1`
for the speaker registry. Each layout selects a random quote, looks up the
speaker by slug, and builds its portrait URL from the speaker's relative image
path. No quote API or quote-baking step is needed. The old generated static
templates were not migrated because they duplicated the quote data in Liquid.
Other sources can have their own Liquid files and image paths rather than
sharing a source-selecting template.

### Configure a TRMNL Private Plugin

Choose the **Polling** strategy and put these two URLs in the Polling URL box,
one URL per line (keep this order so the responses are `IDX_0` and `IDX_1`):

```text
https://raw.githubusercontent.com/Kaskelotval/trmnl-quotes/main/sources/disco-elysium/quotes/quotes.json
https://raw.githubusercontent.com/Kaskelotval/trmnl-quotes/main/sources/disco-elysium/quotes/speakers.json
```

Then paste each matching file from `sources/disco-elysium/templates/` into its
layout tab in TRMNL. These are source-specific layouts; for another source,
provide its quote and speaker JSON URLs and make corresponding templates if
the data or image paths differ. **Static Data does not fetch URLs stored inside
its JSON**; use Polling for these repository files.

TRMNL's Liquid random selection happens when it renders a screen. If TRMNL skips
rendering because the polled JSON responses have not changed, the chosen quote
may not rotate on every scheduled poll; verify refresh behavior with the plugin.

Quote entries currently have this shape:

```json
{
	"id": "dialogue-467:23",
	"type": "single",
	"text": "A quote goes here.",
	"speaker": "volition",
	"location": "Optional location"
}
```

Each source's quote file contains only quotes intended for display, so it does
not repeat the source name or store per-quote approval/safety flags. `id` must
be unique within the source; `type` is retained to allow future exchange-style
quotes.

Speaker metadata lives in
[`sources/disco-elysium/quotes/speakers.json`](sources/disco-elysium/quotes/speakers.json).
Image values are relative to that file, e.g. `../images/volition.png`; `null`
means there is no image. A consumer publishing these assets should resolve the
relative path against the source's `quotes/` directory.

Edit `quotes.json` directly to maintain the runtime collection. Keep quote IDs
unique and preserve the object structure. The optional helper curation pipeline
can also add approved records, but it does not need to be run for normal quote
edits or runtime loading.

## Helpers

The scripts under `helpers/` are a personal assortment of tools cooked up for
the Disco Elysium quote and image work. They are not a generic toolkit or part
of the source-data format, and may be rough or specific to that workflow. Their
paths are computed relative to the repository, not a particular laptop. They
use local working data under `helpers/data/`; large game databases and
intermediate dialogue exports do not belong in this repo.

Typical curation sequence (requires a local `disco.db` file):

1. `python3 helpers/0_extract_from_db.py --db /path/to/disco.db`
2. `python3 helpers/build_speaker_registry.py`
3. `python3 helpers/1_normalize.py`
4. `python3 helpers/2_filter_score.py`
5. `python3 helpers/3_review_cli.py`
6. `python3 helpers/4_build_curated.py`

Use `python3 helpers/prepare_portraits.py` to process local files placed in
`helpers/portraits_raw/` into `sources/disco-elysium/images/` and update speaker
image paths. Raw portrait inputs and generated pipeline intermediates are
ignored by Git; only the processed source images are checked in. The old
static-template baking script was intentionally not moved:
the JSON files are the runtime data now.

## Current sources

- `disco-elysium` — 60 approved quotes and the existing speaker portraits.