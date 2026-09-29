# Recommendation Engine v2 (Collaborative + Content-Based)
### For an Independent Elderly Care Facility — Week 3, Professional/Advanced Build

## Project Scope

The system recommends non-medical activities and social/wellness programs to
residents of an independent elderly care facility. Recommendations are based
on:

1. Resident preferences and interests
2. Previous participation and ratings
3. Similarity between activities
4. Similarity between residents

The system combines content-based filtering and collaborative filtering into
a hybrid recommendation. **The system does not make medical, diagnostic,
medication, or clinical care recommendations.**

## What I Built and Why

A hybrid recommender served as a **live website** (Flask API + HTML/CSS/JS
dashboard), not just a script, with two independent scoring engines
blended by a `HybridEngine`:

- **Content-based filtering** compares a resident's stated interest tags to
  each activity's attribute tags. This works even for a resident with zero
  history — solving the "cold-start" problem collaborative filtering alone
  cannot.
- **Collaborative filtering** builds a resident × activity ratings matrix
  (via `pandas.pivot_table`), mean-centers each resident's ratings to
  correct for generous vs. harsh raters, and uses cosine similarity to find
  residents with similar taste, recommending what those neighbors rated
  highly.
- A **mobility filter** (logistical, not clinical) prevents recommending
  high-intensity activities to residents using a wheelchair or walker,
  directly enforcing the "no medical/clinical recommendations" boundary
  from the scope statement.
- **Implicit behaviour tracking** (`implicit_tracker.py`) observes which
  recommended activities a resident clicks into, without requiring them to
  submit a rating. Scored as click-through rate (clicks ÷ impressions) so
  an activity clicked once out of one impression isn't treated the same as
  one clicked once out of twenty — see "Three-signal blend" below.

### The live feedback loop

The website lets anyone: browse an existing resident's recommendations,
register as a brand-new resident (interests + mobility, no history needed),
and log feedback ("attended" + a 1-5 rating) on a recommended activity.
Every logged interaction is written to `data/live_interactions.csv` and
every new resident to `data/live_residents.csv` — kept separate from the
original synthetic dataset so the data lineage stays honest. After each
write, the Flask backend **refits both recommenders from scratch** using
the combined synthetic + live data, so the very next recommendation
request — for *any* resident, not just the one who just acted — reflects
that new information. This is the actual difference between a one-off
script and a real recommendation engine: it learns from usage.

### Three-signal blend: explicit, collaborative, and implicit

`HybridEngine` combines three signals, not two, each normalized to a 0-1
scale before blending so no signal dominates just because its raw numbers
happen to be bigger:

| Signal | Source | Requires effort from resident? | Weight |
|---|---|---|---|
| Content-based | stated interests vs. activity tags | No | shares the "primary" 85% with collaborative |
| Collaborative | explicit attended + star rating | Yes (rate something) | shares the "primary" 85% with content |
| Implicit | clicked a recommendation card | No (just browsing) | fixed 15% |

Implicit signal is deliberately capped at a small, fixed weight rather than
competing equally with the other two — a click is weak, easily accidental
evidence of interest, while an actual attended-and-rated visit is strong
evidence. This is a judgment call, documented here rather than left
implicit (no pun intended) in the code. Impressions are logged
server-side the instant recommendations are returned (`HybridEngine`
itself calls `implicit_tracker.log_impressions(...)`); clicks are logged
from the frontend (`static/app.js`) the moment a resident opens a card.

### Age and gender: intentionally excluded from scoring

Both fields are collected and stored (`residents.csv`), but neither feeds
into any recommender. This was a deliberate decision, not an oversight:
both are weak predictors of activity preference relative to stated
interests and rating history, and using them risks encoding stereotypes
(e.g. "women get knitting," "older residents get bingo") into the ranking.
`gender` was generated independently of interest tags in the synthetic
dataset specifically so it can support a fairness audit — comparing
recommendation distributions across the field — without ever being an
input to the recommendations themselves. See "What I'd Improve" below.

## Architecture

```
Browser (static/app.js)
     | fetch()
     v
Flask routes (app.py)
     |
     v
DataLoader --> ContentRecommender + CollaborativeRecommender --> HybridEngine
     |
     v
JSON response --> rendered as recommendation cards, stats, and a live feed
```

`app.py` exposes:
- `GET /api/residents`, `POST /api/residents` — list / register residents
- `GET /api/recommendations/<resident_id>` — ranked recommendations, with a
  `content_weight` query param to live-tune the content/collaborative blend
- `POST /api/interactions` — log attendance + rating, triggers a refit
- `POST /api/events` — log an implicit click (no rebuild needed; implicit
  scores are read fresh from disk on every request, so this stays instant)
- `GET /api/stats` — facility-wide category popularity, recent activity
  feed, and total impressions/clicks tracked

## Dataset

Real facility data is private and inaccessible, so a synthetic but
realistic dataset was generated with a seeded script (`generate_dataset.py`)
for reproducibility: 45 residents, 33 activities across 8 realistic
categories (Fitness & Movement, Arts & Crafts, Social & Games, Music &
Entertainment, Educational & Cognitive, Outdoor & Nature, Spiritual &
Reflection, Culinary), and 533 interaction records. Attendance and ratings
are weighted toward tag overlap with each resident's stated interests, with
random noise added, so the data has genuine (not artificial) signal for
both recommenders to detect.

**Design decisions worth noting:**
- 200 of 533 ratings are missing — but every missing rating corresponds to
  `attended = False`. This is *structurally* missing data (you can't rate
  something you didn't attend), not a data quality gap, so it was
  deliberately **not imputed**. Filling it would invent opinions residents
  never had and corrupt the collaborative signal.
- `age` and `gender` are stored but intentionally **excluded from
  scoring** — they are weak predictors here and risk encoding stereotypes
  (e.g. "women get knitting"). `gender` was generated independently of
  interests in the synthetic data specifically so it could be used for a
  fairness audit rather than as a recommendation input.

## Tools and Techniques

- **Pandas**: `pivot_table` for the ratings matrix, boolean masking,
  `groupby`-adjacent aggregation, vectorized scoring.
- **NumPy**: cosine similarity via vectorized dot products.
- **Flask**: REST API serving JSON to a vanilla HTML/CSS/JS frontend.
- No external ML library — similarity logic was hand-built to understand
  the mechanics before reaching for `scikit-learn`.

## What I Tested

See `evaluator.py` / console output from `main.py`. Six checks, all
passing:

1. **Existing resident** — recommendations exclude previously attended
   activities.
2. **New resident, no history (cold-start)** — falls back cleanly to
   content-based scoring only.
3. **Resident with missing interests** — does not crash; returns
   exploratory recommendations.
4. **Wheelchair mobility filter** — a resident with high-intensity
   interests still receives only low-intensity recommendations, proving
   the filter overrides raw interest matching.
5. **Never-rated activity** — pipeline handles activities with zero
   ratings without errors.
6. **Implicit signal cold-start** — a resident with zero clicks yet gets a
   clean `implicit_score = 0` rather than an error, confirming the
   three-signal blend degrades gracefully when one signal is empty.

I also manually verified the live feedback loop end-to-end: logging a
click on a recommended activity raised its `implicit_score` from 0.0 to
1.0 (1 click / 1 impression) on the very next request, and its
`hybrid_score` rose accordingly — confirming the "observed behaviour"
requirement actually changes ranking, not just gets logged and ignored.

## What I'd Improve With More Time

- Replace hand-built cosine similarity with `scikit-learn`'s
  implementation and benchmark against it.
- Run the fairness audit across `gender` that the data already supports,
  rather than just leaving the field available for one.
- Tune `content_weight` / `collab_weight` / `implicit_weight` against
  held-out interaction data instead of fixed defaults.
- Add time-decay so older ratings and older clicks count less than recent
  ones.
- Move from CSV + in-memory refit to a real database (e.g. SQLite/Postgres)
  and a production WSGI server (gunicorn) instead of Flask's dev server,
  for genuine multi-user concurrent use.

## How to Run

```bash
pip install -r requirements.txt
python generate_dataset.py   # regenerates data/*.csv (optional, already included)
python main.py                # CLI: runs recommendations + evaluation suite in the terminal
python app.py                  # website: starts Flask at http://127.0.0.1:5000
```

## Project Structure

```
eldercare_reco/
├── data/                          # residents.csv, activities.csv, interactions.csv
│                                    # (live_interactions.csv / live_residents.csv /
│                                    #  live_implicit_events.csv appear here once the
│                                    #  website starts logging real usage)
├── generate_dataset.py            # synthetic data generator (seeded, reproducible)
├── data_loader.py                 # DataLoader — reads base + live CSVs
├── interaction_logger.py          # InteractionLogger — writes live interactions/residents
├── implicit_tracker.py            # ImplicitTracker — impressions/clicks -> click-through rate
├── content_recommender.py         # ContentRecommender — tag-overlap + mobility filter
├── collaborative_recommender.py   # CollaborativeRecommender — pivot table + cosine similarity
├── hybrid_engine.py               # HybridEngine — normalizes + blends all three scores
├── evaluator.py                   # Evaluator — required test suite
├── main.py                        # CLI entry point
├── app.py                          # Flask API + website entry point
├── templates/index.html            # dashboard page (includes wellness-only disclaimer)
├── static/style.css                # dashboard styling
├── static/app.js                   # dashboard frontend logic (fetch calls to the API)
├── requirements.txt
└── README.md
```