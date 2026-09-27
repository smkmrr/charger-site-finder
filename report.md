# Fördjupning i Pythonprogrammering — Uppgift 2

**Ali Akyel · EC Utbildning · September 2026**
Code: [github.com/smkmrr/charger-site-finder](https://github.com/smkmrr/charger-site-finder)

---

## Purpose

I wanted to learn how to build an **ingestion layer** in Python: the part of a data
project that reaches out to external HTTP APIs, survives their failures, and turns
their untyped JSON into typed objects the rest of the program can trust.

The scope I set for myself was deliberately narrow. Not "learn about APIs", but:
fetch from two unrelated public APIs, retry the failures that are worth retrying,
cache the responses so the project can be run and graded without live access, and
validate every record at the boundary so that no later function has to wonder
whether a coordinate exists or a power value is a number.

To have something real to build it on, I used a question from my current work —
where could new EV charging stations be placed in Ankara — but the siting question
is the motivation, not the subject. The subject is the layer underneath it.

## The area and why it matters

Every data project starts with getting data in, and the sources rarely agree on
field names, units, or what counts as a missing value. Between a public API and a
DataFrame there is a layer that is usually written in a hurry and then quietly
becomes the most fragile part of the pipeline.

Three things in that layer decide whether an analysis can be trusted:

- **Failure handling.** A network call fails for two very different reasons. The
  server is busy, or the request itself is wrong. Treating these the same way
  produces either a pipeline that crashes on a hiccup, or one that hammers a
  source a hundred times with a request that will never be accepted.
- **Caching.** An analysis that cannot be re-run is not reproducible. If the
  source has disappeared, changed, or rate limited me, a cached response is the
  difference between a result I can defend and one I have to take on faith.
- **Validation at the boundary.** Bad data that enters silently is found much
  later, usually in a chart nobody questions. Catching it at arrival, and keeping
  what was rejected, turns a silent error into a visible number.

None of this is specific to charging stations. It is the same for a Data Scientist
pulling from an internal API, a public register, or a vendor's endpoint.

## Key concepts

**HTTP client and timeouts.** `httpx` is a modern HTTP client with an API close to
`requests` but with explicit timeout control. I set a short connect timeout and a
long read timeout (`httpx.Timeout(10.0, read=120.0)`), because the two mean
different things: failing to reach the server is a problem, while a slow body is
expected — EPDK's response is around 16 MB.

**Transient versus permanent failures.** A 429 ("too many requests") or a 5xx
means "not now"; a 400, 401, 403 or 404 means "not like this". Only the first kind
is worth retrying. In the code this distinction is one line:

```python
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
```

**Retry with exponential backoff.** `tenacity` provides this as a decorator. Each
attempt waits longer than the last — 2, 4, then 8 seconds. The growing pause
matters: if a server is already overloaded, retrying immediately makes it worse.

**Caching.** A response is written to disk and reused while it is younger than a
set age. This makes runs fast, keeps the project inside the source's rate limit,
and makes the result reproducible.

**Fixture.** A trimmed copy of a real response, committed to the repository, used
when the source cannot be reached at all. It is what makes the project runnable by
someone who clones it.

**Validation at the boundary.** `Pydantic` v2 turns an untyped `dict` into a typed
object and refuses the ones that do not fit. A coordinate is declared as
`Field(ge=-90, le=90)`; a socket's power as `Field(gt=0)`. Once a record has passed
the model, no later code needs to check it again — the doubt is concentrated in one
place instead of being spread over every function.

**Rejection record.** A record that fails validation is not dropped. It is stored
as a small object with its source, identifier and reason, and written to its own
CSV. A number I can see is worth more than a record silently missing.

## Implementation

### Sources and how they were chosen

My approved proposal named Open Charge Map as the station source. I changed it
after measuring rather than arguing: Open Charge Map returned **73** stations for
Ankara, while EPDK's national register returned **16 885** for Turkey. The gap is
not technical but structural — Open Charge Map is crowdsourced, while EPDK is the
energy regulator and every licensed operator is legally obliged to file its
stations. For this question the mandatory register is simply the better source.

EPDK publishes two different APIs, and telling them apart cost me time. One
(`sarjotomasyon.epdk.gov.tr`) requires a licence login and returns only the
caller's own stations — useless here. The public one
(`apigateway.epdk.gov.tr/sarjIstasyonlari`) returns the whole register without
authentication.

Candidate locations come from **OpenStreetMap** through the Overpass API. The
selection happens in the query itself rather than in a later filter: the Overpass
query asks only for `shop=mall`, `amenity=hospital`, `amenity=clinic` and
`building=office` inside the bounding box, so unwanted categories never arrive.

Neither source needs an API key, so the project stores no secrets at all.

### Structure

The package is split so that each module has one job and the dependencies point in
one direction. `config.py` imports nothing from the package and holds the search
area and the business thresholds; `models.py` defines the types every source is
normalised into; `http_client.py` is the only module that touches the network;
`epdk.py` and `overpass.py` translate one source each; `distance.py`,
`screening.py` and `reporting.py` work purely on validated objects and never see
JSON; `cli.py` sits at the outside and is the only place that configures logging.

### Technical choices worth defending

**One transport layer for both sources.** `fetch_json` tries three things in
order: a cached response younger than seven days, then the network with retries,
then the bundled fixture. Both sources go through it, so caching and retry
behaviour cannot drift apart between them.

**A fixture is never written into the cache.** This looks like a small detail and
is not. If a fallback response were cached, a two-minute outage would turn into a
week of silently stale data. The fixture is returned and a warning is logged, but
the cache stays empty so the next run tries the network again.

**Models are frozen.** `ConfigDict(frozen=True)` makes a validated record
immutable. A `Station` that has passed validation cannot be modified later by
accident, so "valid at arrival" also means "valid at use".

**Rejections are data, not exceptions.** Each source loop validates one record at
a time and appends a `Rejection` when it fails, instead of aborting the batch. The
catch is narrow — `ValidationError`, `KeyError`, `TypeError` — so a real bug in my
own code still surfaces as a crash instead of being filed away as bad input.

**A cheap filter before an expensive one.** Before computing any distances, the
stations are reduced to the public ones inside the bounding box — 16 885 down to
962 — using four comparisons per record. Only then does the haversine calculation
run, and only against that subset.

**Broad exception handling in exactly one place.** `cli.py` catches `Exception`,
logs a readable message and returns exit code 1, so the user sees a sentence
instead of a traceback. The linter flags this correctly as a code smell; I
suppressed it on that single line with a comment explaining why the outer boundary
is the one place where it is right.

**Pinned versions.** Every dependency is pinned to the exact version I tested
with, so a fresh clone resolves to the same libraries.

### Problems I ran into

**EPDK rejected every request with 400.** The message was
`JSON Schema Validation policy failed`. The gateway requires a JSON body — even on
a GET. `httpx.get()` refuses to send a body, which is why the code calls
`httpx.request("GET", url, json={})` instead. A GET with a body is undefined
rather than forbidden by RFC 9110, and this gateway depends on it.

**One request per hour.** Unparameterised calls to EPDK are rate limited, which
meant a grader could not simply run the tool twice. This is the reason the fixture
fallback exists, and I verified it by pointing the client at an unreachable
hostname: three retries with growing pauses, then the fixture, then 1 540 records.

**Overpass returned 504.** This one I did not have to handle specially — the
retry caught it. The log shows a 504, a two-second pause and a 200.

**285 OpenStreetMap elements had no name.** An unnamed location is useless on a
sales card, so `name` is mandatory in the model and those records are rejected.
They are not lost: they are written out with their reason.

## Results

A full run over the Ankara bounding box:

```
stations from EPDK      : 16885
public, inside the area : 962
candidates from OSM     : 401
cards written           : 363
records quarantined     : 285
```

Of 686 OpenStreetMap elements, 401 passed validation and 285 were rejected for a
missing name. All 16 885 EPDK records passed — which says something about the
difference between crowdsourced and regulated data. Of the 401 candidates, 38 were
dropped because one of our own brands already has a DC socket above 60 kW within
200 m, leaving 363 location cards.

Note that these two exclusions are different in kind. A rejection means the record
was unusable and is written to its own file with a reason. A candidate covered by
our own brand is a perfectly valid record that simply has no business value — it
produces no card, and no rejection either.

The output is two timestamped CSV files, written with a UTF-8 BOM so that Turkish
characters survive being opened in Excel. Example output from a real run is
committed in `data/examples/`.

Two runs show the failure paths working, both taken from real logs:

```
POST overpass-api.de "HTTP/1.1 504 Gateway Timeout"
WARNING Retrying _request in 2 seconds — RetryableStatusError: 504
POST overpass-api.de "HTTP/1.1 200 OK"
```

```
WARNING Retrying _request in 2 seconds — ConnectError
WARNING Retrying _request in 4 seconds — ConnectError
WARNING Retrying _request in 8 seconds — ConnectError
WARNING could not reach epdk — falling back to the bundled fixture
records from fixture: 1540
```

## Limitations and possible improvements

**The register lags the field.** A station enters EPDK's data only after it is
built, inspected and licensed. A station that is physically standing but still
waiting for its licence is invisible, so the tool can mark a location as free when
a competitor is already there. The error goes one way only — coverage is
underestimated, never overestimated — which makes the output safe to act on with a
site visit, but not safe to act on blindly.

**`amenity=clinic` is too broad.** OpenStreetMap uses the same tag for a
hospital's outpatient unit and for a two-room dental practice. A small surgery is
not a realistic charging site, but nothing in the code separates the two, so both
end up as cards. A filter on size or sub-type is the fix. I noticed this while
reading the output and deliberately left it for later rather than inventing a
threshold under time pressure.

**One bounding box.** The area is a rectangle defined in `config.py`. Screening a
whole country would need either a list of boxes or a different query strategy,
since Overpass limits how much can be asked for at once.

**Haversine, not geodesic.** Distances treat the Earth as a sphere. Over 200 m the
error is far below the uncertainty in the coordinates themselves, so it is the
right approximation here — but it would not be for long distances.

**No automated tests.** I verified behaviour by running the tool and by forcing
failures by hand, for example by pointing it at an unreachable hostname. That is
evidence, but it is not repeatable by someone else. Tests for the validation rules
and for the retry decision would be the first thing I add.

**The extras I did not do.** My topic approval listed three optional extensions:
comparing `httpx` with `requests`, adding further station sources, and measuring
synchronous against asynchronous fetching. I prioritised the core — two sources,
validation, error handling and caching — as instructed, and did not reach these.
Async is the most interesting of the three. A run makes two requests, so
overlapping them would save seconds at best; it would matter if the tool screened
many areas at once, where a dozen Overpass calls could run concurrently instead of
one after another.

**Comparing snapshots.** Output files are timestamped, so two runs a month apart
can be compared to see what changed in the register. The comparison itself is not
implemented.

## Relevance to the professional role

This layer is the part of a data role that nobody writes about and everybody
depends on. A Data Scientist who pulls from an internal API, a public register or
a vendor endpoint faces the same three questions: what do I do when the call
fails, how do I make this run reproducible, and how do I know the data is what I
think it is.

The specific habits transfer directly. Distinguishing transient from permanent
failures is what keeps a scheduled job from either dying on a hiccup or retrying a
bad credential all night. Caching is what lets someone re-run my analysis in six
months. Validating at the boundary, and counting what was rejected, is what turns
"the numbers look a bit off" into "285 records were dropped, here they are, here
is why".

In my current work the output is a list of locations for a sales team. In a data
role the output would be a table for a model or a dashboard. The layer underneath
is the same one.

## Sources

- httpx documentation — <https://www.python-httpx.org/>
- tenacity documentation — <https://tenacity.readthedocs.io/>
- Pydantic v2 documentation — <https://docs.pydantic.dev/latest/>
- Overpass API user manual and OpenStreetMap wiki — <https://wiki.openstreetmap.org/wiki/Overpass_API>
- EPDK public charging station API — <https://apigateway.epdk.gov.tr/sarjIstasyonlari>
- RFC 9110, *HTTP Semantics*, on GET request bodies — <https://www.rfc-editor.org/rfc/rfc9110>
- PEP 695, *Type Parameter Syntax* — <https://peps.python.org/pep-0695/>
- Python standard library documentation for `argparse`, `csv` and `logging`
- OpenStreetMap data © OpenStreetMap contributors, Open Database License (ODbL)

---

## Self-reflection

**1. What did you learn that you could not do before?**

Two things, one technical and one not.

The technical one: error handling is a design decision, not a safety net added at
the end. Before this I would have wrapped a request in `try/except` and moved on.
Now I think in terms of which failures deserve another attempt and which do not,
and where in the program a failure should be allowed to stop everything. The same
goes for validation at the boundary — it does not only catch bad data, it removes
the need to be suspicious everywhere else.

The other one came from building on a real business case. Because I know the field
work, I kept feeling an urge to make the tool cover every situation a person would
handle by hand. But the data gave me far more prospects than the manual process
ever produced, and covering everything would have meant finishing nothing. So I
had to prioritise: set a threshold, keep the excluded items in a separate list to
revisit rather than deleting them, and keep asking what the tool is ultimately
for. What I learned is that an under-specified business case does not stay a
business problem — it turns into technical decisions that someone has to make, and
that someone was me. It is also the same idea as the rejection file: do not throw
anything away, set it aside with a reason.

**2. What was hardest to understand or carry out?**

EPDK's gateway returning 400 to what looked like a perfectly ordinary GET. The
answer was that it required a JSON body on a GET — something `httpx.get()` refuses
to send on purpose, because a GET with a body is outside what the HTTP
specification defines. Understanding *why* the library refused, rather than just
finding a call that worked, took the longest.

**3. Which technical choice are you most satisfied with, and why?**

That a fixture is never written into the cache. It is one decision with three
lines of consequence, and it is the kind of thing that only bites weeks later: a
short outage would otherwise have become seven days of stale data that looked
completely normal. Second place goes to keeping rejected records instead of
dropping them — it is what turned "OpenStreetMap gave me some places" into "686
in, 401 valid, 285 rejected, and here is each reason".

**4. What would you do differently if you started over?**

Check the source before committing to it. I chose Open Charge Map because it was
open and well known, and started building against it without ever testing whether
it actually held the field data I needed. It did not — 73 stations for a city with
thousands. The lesson is not "I picked the wrong source"; it is that I did not yet
know which criteria to check before picking one. Coverage for my actual area, and
how the data gets in, would both have been one API call away.

I would also have written a few tests along the way instead of planning to add
them afterwards.

**5. What would be a natural next step?**

Tests for the validation rules and the retry decision, since those are the two
places where a silent change would do the most damage. Then the `amenity=clinic`
problem, and then comparing two timestamped runs to show what changed in the
register between them.

**6. Which grade do you think the work corresponds to — G or VG?**

VG.

**7. Motivate your assessment against the criteria.**

The G requirements are met: the area is a Python deepening relevant to the data
role, the scope was set and kept, the solution runs, the code is structured and
documented, and the work was presented in writing and orally.

For VG I would point at four things. The technical choices are mine and I can give
the reason for each — why only 429 and 5xx are retried and 404 never is, why the
fixture stays out of the cache, why the models are frozen, why a broad `except`
belongs at the CLI boundary and nowhere else. I explain why the techniques work
rather than only showing that they do; the difference between a transient and a
permanent failure is the argument the whole retry design rests on. I made a source
decision by measuring instead of assuming, and I can state what I gave up: a
register that lags the field, in a direction I can describe. And the failure paths
are demonstrated with real logs rather than described — a 504 that recovered on the
second attempt, and an unreachable host that fell through three retries into the
fixture.

What argues against VG is the absence of automated tests. I verified the behaviour
by running it and by forcing failures by hand, which is evidence but not repeatable
evidence, and it is the first gap I would close.
