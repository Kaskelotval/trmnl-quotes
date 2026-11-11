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

For example, a consumer can fetch the live collection and select a safe,
approved quote like this:

```js
const response = await fetch(
	"https://raw.githubusercontent.com/Kaskelotval/trmnl-quotes/main/sources/disco-elysium/quotes/quotes.json",
);
const { quotes } = await response.json();
const pool = quotes.filter(
	(quote) => quote.status === "approved" && quote.display_safe !== false,
);
const quote = pool[Math.floor(Math.random() * pool.length)];
```

Alternatively, bundle/import the JSON file in the consuming application.

## Templates

The Disco Elysium layouts are in
[`sources/disco-elysium/templates/`](sources/disco-elysium/templates/). They
render the `quote` object supplied by the polling/API layer and contain no
quote corpus or random selection logic. That layer should read the source JSON,
select a quote, and return the normalized `{"quote": ...}` payload. The old
generated static templates were not migrated because they duplicate the quote
data in Liquid. Other sources can have their own Liquid files and image paths
rather than sharing a source-selecting template.

Quote entries currently have this shape:

```json
{
	"id": "dialogue-467:23",
	"status": "approved",
	"type": "single",
	"text": "A quote goes here.",
	"speaker": "volition",
	"game": "Disco Elysium",
	"location": "Optional location",
	"context": null,
	"source_id": "467:23",
	"display_safe": true
}
```

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