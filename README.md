# charger-site-finder

Finds candidate locations for new EV charging stations inside a bounding box by
combining two independent public data sources: places where people already spend
time (OpenStreetMap) and the charging stations that already exist (Turkey's
national registry, EPDK).

The written report for the assignment, including the self-reflection, is in
[`report.md`](report.md).

## What it does

1. Fetches candidate places from the Overpass API (OpenStreetMap) inside the
   configured bounding box: malls, hospitals, clinics and office buildings.
2. Fetches every licensed charging station from EPDK's national registry.
3. Validates each record against a Pydantic model. Records that fail are not
   dropped — they are quarantined with their source, identifier and reason.
4. Keeps the candidates that have no station of our own brands above 60 kW DC
   within 200 m, and notes nearby competitor stations as commercial context.
5. Writes two timestamped CSV files: the location cards and the rejected records.

## Requirements

Python 3.12 or newer. The code uses PEP 695 type parameter syntax, which 3.11
cannot parse.

## Install

```bash
git clone https://github.com/smkmrr/charger-site-finder.git
cd charger-site-finder
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

```bash
charger-finder --area ankara
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--area {ankara}` | which configured search area to screen | `ankara` |
| `--radius-km` | an existing station within this distance covers a candidate | `0.2` |
| `-v`, `--verbose` | show DEBUG level logging | off |

Output is written to `data/output/` as `cards_<area>_<timestamp>.csv` and
`rejected_<area>_<timestamp>.csv`. Example output from a real run is committed in
`data/examples/`, so the result can be inspected without running the tool.

A run ends with a summary:

```
stations from EPDK      : 16885
public, inside the area : 962
candidates from OSM     : 401
cards written           : 363
records quarantined     : 285
```

## Dependencies

- `httpx` 0.28.1 — HTTP client
- `pydantic` 2.13.5 — validation at the boundary
- `tenacity` 9.1.4 — retry with exponential backoff

The `dev` extra adds `ruff` for linting and formatting.

## Data and external services

Both sources are public and **neither requires an API key or any other
authentication**. No keys, passwords or tokens are needed, and none are stored in
this repository.

**EPDK** — `https://apigateway.epdk.gov.tr/sarjIstasyonlari`
Turkey's Energy Market Regulatory Authority publishes every licensed charging
station, with coordinates, brand, access type and sockets. The gateway rejects a
GET without a body, so the request is sent as a GET carrying an empty JSON object.
Unparameterised calls are rate limited to roughly one per hour.

**OpenStreetMap**, via the Overpass API — `https://overpass-api.de/api/interpreter`
Map data © OpenStreetMap contributors, available under the Open Database License
(ODbL).

## Configuration

Everything configurable lives in `src/charger_finder/config.py`: the bounding box,
the brand list, the power thresholds, the search radius and the cache lifetime.
The project reads no environment variables.

## Caching and offline use

Every request goes through one transport layer that tries three things in order:
a cached response younger than 7 days, then the network, then the trimmed copy
committed in `data/fixtures/`. Only transient failures are retried — timeouts,
connection errors, 429 and 5xx — with a backoff of 2, 4 and 8 seconds.

A fresh clone therefore produces output even with no network access or when
EPDK's rate limit has been reached. Cached responses in `data/cache/` are not
committed; the fixtures are. A fixture is never written into the cache, so a
short outage cannot turn into a week-old cache entry.

## Project layout

```
src/charger_finder/
    config.py        settings, search areas and business thresholds
    models.py        the Pydantic models every source is normalised into
    http_client.py   cache, retry and fixture fallback
    epdk.py          the national station registry
    overpass.py      OpenStreetMap candidate places
    distance.py      haversine distance and spatial filters
    screening.py     the business rules that turn candidates into cards
    reporting.py     CSV output and the run summary
    cli.py           argument parsing and the outer error boundary
```

`scripts/make_fixtures.py` rebuilds the fixtures from a full cached response.
