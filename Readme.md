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

A hybrid recommender with two independent scoring engines, blended by a
`HybridEngine`:

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
- No external ML library — similarity logic was hand-built to understand
  the mechanics before reaching for `scikit-learn`.

## What I Tested

See `evaluator.py` / console output from `main.py`. Five checks, all
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

## What I'd Improve With More Time

- Replace hand-built cosine similarity with `scikit-learn`'s
  implementation and benchmark against it.
- Add a formal fairness audit comparing recommendation distributions across
  the `gender` field (data already supports this).
- Tune `content_weight` / `collab_weight` against held-out interaction data
  instead of a fixed 0.5/0.5 split.
- Add time-decay so older ratings count less than recent ones.

## How to Run

```bash
pip install -r requirements.txt
python generate_dataset.py   # regenerates data/*.csv (optional, already included)
python main.py                # runs recommendations + evaluation suite
```

## Project Structure

```
eldercare_reco/
├── data/                          # residents.csv, activities.csv, interactions.csv
├── generate_dataset.py            # synthetic data generator (seeded, reproducible)
├── data_loader.py                 # DataLoader — single source of truth for CSV access
├── content_recommender.py         # ContentRecommender — tag-overlap + mobility filter
├── collaborative_recommender.py   # CollaborativeRecommender — pivot table + cosine similarity
├── hybrid_engine.py               # HybridEngine — normalizes + blends both scores
├── evaluator.py                   # Evaluator — required test suite
├── main.py                        # entry point
├── requirements.txt
└── README.md
```