"""
app.py

Flask backend for the Elder Care Activity Recommender website.

FLOW:
  Browser (static/app.js)
       | fetch()
       v
  Flask routes (this file)
       |
       v
  DataLoader -> ContentRecommender + CollaborativeRecommender -> HybridEngine
       |
       v
  JSON response back to the browserr

THE FEEDBACK LOOP (the actual "real recommendation engine" behavior you
asked for): every time someone logs feedback (POST /api/interactions) or a
new resident registers (POST /api/residents), we call rebuild_engine(),
which re-reads ALL data (synthetic + live) and refits both recommenders.
The very next recommendation request -- for ANY resident, not just the one
who just acted -- reflects that new data. This is what makes it a live
recommender instead of a one-off script.

THREADING NOTE: Flask's built-in dev server is fine for this project
(single-user demo/portfolio use). A `threading.Lock` guards rebuild_engine()
so a read never happens mid-rebuild. In a real multi-user production
deployment you'd replace the in-memory engine with a proper database and a
task queue -- documented as a "with more time" improvement in the README.
"""

import os
import threading
import pandas as pd
from flask import Flask, jsonify, request, render_template

from data_loader import DataLoader
from content_recommender import ContentRecommender
from collaborative_recommander import CollaborativeRecommender
from hybrid_engine import HybridEngine
from interaction_logger import InteractionLogger
from implicit_tracker import ImplicitTracker

app = Flask(__name__)
logger = InteractionLogger(data_dir="data")
implicit_tracker = ImplicitTracker(data_dir="data")

_state = {"loader": None, "engine": None}
_lock = threading.Lock()


def rebuild_engine():
    """Re-reads all EXPLICIT data (synthetic + live) and refits both recommenders.
    Implicit (click/impression) data does NOT require a rebuild -- ImplicitTracker
    reads its file fresh on every request, so clicks take effect immediately
    without this heavier refit step.
    """
    loader = DataLoader(data_dir="data").load_all()
    content = ContentRecommender().fit(loader.activities_df)
    collaborative = CollaborativeRecommender().fit(loader.interactions_df)
    engine = HybridEngine(content, collaborative, implicit_tracker=implicit_tracker)
    with _lock:
        _state["loader"] = loader
        _state["engine"] = engine


def get_state():
    with _lock:
        return _state["loader"], _state["engine"]


# Build the engine once at startup so the first request doesn't pay the cost.
rebuild_engine()


# ---------------------------------------------------------------------------
# PAGE
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API: residents
# ---------------------------------------------------------------------------
@app.route("/api/residents", methods=["GET"])
def list_residents():
    loader, _ = get_state()
    residents = loader.residents_df[["resident_id", "name", "mobility_level", "interests"]]
    return jsonify(residents.to_dict(orient="records"))


@app.route("/api/residents", methods=["POST"])
def register_resident():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    interests = data.get("interests") or []
    mobility_level = data.get("mobility_level") or "independent"

    if not interests:
        return jsonify({"error": "Please select at least one interest."}), 400

    resident_id = logger.register_resident(name, interests, mobility_level)
    rebuild_engine()  # new resident should be visible immediately
    return jsonify({"resident_id": resident_id}), 201


# ---------------------------------------------------------------------------
# API: activities (used to populate the interest-tag picker on the frontend)
# ---------------------------------------------------------------------------
@app.route("/api/activities", methods=["GET"])
def list_activities():
    """
    Full activity catalog, with optional server-side filtering:
      - ?q=<text>       matches against name, category, or tags (case-insensitive)
      - ?category=<cat> exact category match
    Powers the "Browse all activities" tab -- independent of any resident's
    personalized recommendations, the way a real app's catalog/search page
    would be.
    """
    loader, _ = get_state()
    df = loader.activities_df.copy()

    q = request.args.get("q", default="", type=str).strip().lower()
    if q:
        haystack = (
            df["name"].str.lower() + " " +
            df["category"].str.lower() + " " +
            df["tags"].str.lower()
        )
        df = df[haystack.str.contains(q, na=False)]

    category = request.args.get("category", default="", type=str).strip()
    if category:
        df = df[df["category"] == category]

    return jsonify(df.to_dict(orient="records"))


@app.route("/api/categories", methods=["GET"])
def list_categories():
    """Every distinct activity category, for the browse tab's filter chips."""
    loader, _ = get_state()
    return jsonify(sorted(loader.activities_df["category"].unique().tolist()))


@app.route("/api/interest-tags", methods=["GET"])
def list_interest_tags():
    """Every unique tag used across activities, for the interest picker."""
    loader, _ = get_state()
    all_tags = set()
    for tags in loader.activities_df["tags"]:
        all_tags.update(str(tags).split(","))
    return jsonify(sorted(all_tags))


# ---------------------------------------------------------------------------
# API: recommendations
# ---------------------------------------------------------------------------
@app.route("/api/recommendations/<resident_id>", methods=["GET"])
def get_recommendations(resident_id):
    loader, engine = get_state()

    resident_row = loader.get_resident(resident_id)
    if resident_row is None:
        return jsonify({"error": f"Resident '{resident_id}' not found."}), 404

    # Optional weight sliders from the frontend, e.g. ?content_weight=0.7
    content_weight = request.args.get("content_weight", default=0.5, type=float)
    engine.content_weight = max(0.0, min(1.0, content_weight))
    engine.collab_weight = 1.0 - engine.content_weight

    n = request.args.get("n", default=5, type=int)
    history_ids = set(loader.get_resident_history(resident_id)["activity_id"])
    recs = engine.recommend(resident_row, history_ids, n=n)

    recs["explanation"] = recs.apply(lambda row: engine.explain(row), axis=1)
    columns = ["activity_id", "name", "content_score", "collab_score_raw",
               "implicit_score", "hybrid_score", "source", "explanation"]
    result = recs[columns].fillna(0).to_dict(orient="records")

    # attach category/physical_intensity for nicer frontend display
    activities_lookup = loader.activities_df.set_index("activity_id")
    for r in result:
        extra = activities_lookup.loc[r["activity_id"]]
        r["category"] = extra["category"]
        r["physical_intensity"] = extra["physical_intensity"]
        r["duration_min"] = int(extra["duration_min"])

    return jsonify({
        "resident": {
            "resident_id": resident_row["resident_id"],
            "name": resident_row["name"],
            "interests": resident_row["interests"],
            "mobility_level": resident_row["mobility_level"],
        },
        "recommendations": result,
    })


# ---------------------------------------------------------------------------
# API: implicit signals -- clicks, logged from the frontend the moment a
# resident's card is opened. No rating required. See implicit_tracker.py.
# ---------------------------------------------------------------------------
@app.route("/api/events", methods=["POST"])
def log_event():
    data = request.get_json(force=True)
    resident_id = data.get("resident_id")
    activity_id = data.get("activity_id")
    if not resident_id or not activity_id:
        return jsonify({"error": "resident_id and activity_id are required."}), 400

    implicit_tracker.log_click(resident_id, activity_id)
    # Deliberately NOT calling rebuild_engine() here -- implicit scores are
    # read fresh from disk on every recommend() call, so this stays cheap
    # and near-instant, unlike explicit feedback which needs a full refit.
    return jsonify({"status": "logged"}), 201


# ---------------------------------------------------------------------------
# API: logging feedback (the "record data" part of the feedback loop)
# ---------------------------------------------------------------------------
@app.route("/api/interactions", methods=["POST"])
def log_interaction():
    data = request.get_json(force=True)
    resident_id = data.get("resident_id")
    activity_id = data.get("activity_id")
    attended = bool(data.get("attended"))
    rating = data.get("rating")

    if not resident_id or not activity_id:
        return jsonify({"error": "resident_id and activity_id are required."}), 400
    if attended and rating not in [1, 2, 3, 4, 5]:
        return jsonify({"error": "rating must be 1-5 when attended is true."}), 400

    logger.log_interaction(resident_id, activity_id, attended, rating)
    rebuild_engine()  # this is the step that makes it a REAL recommender:
    # the next person's recommendations now reflect this new data point.

    return jsonify({"status": "logged"}), 201


# ---------------------------------------------------------------------------
# API: facility-wide stats, for the dashboard's insights panel
# ---------------------------------------------------------------------------
@app.route("/api/stats", methods=["GET"])
def stats():
    loader, _ = get_state()
    attended = loader.get_attended_only()

    category_counts = (
        attended.merge(loader.activities_df[["activity_id", "category"]], on="activity_id")
        ["category"].value_counts().to_dict()
    )

    implicit_totals = {"total_impressions": 0, "total_clicks": 0}
    if os.path.exists(implicit_tracker.path):
        events = pd.read_csv(implicit_tracker.path)
        implicit_totals["total_impressions"] = int((events["event_type"] == "impression").sum())
        implicit_totals["total_clicks"] = int((events["event_type"] == "click").sum())

    return jsonify({
        "total_residents": int(len(loader.residents_df)),
        "total_activities": int(len(loader.activities_df)),
        "total_interactions": int(len(loader.interactions_df)),
        "total_attended": int(len(attended)),
        "category_popularity": category_counts,
        "recent_activity": logger.get_recent_interactions(8).to_dict(orient="records"),
        **implicit_totals,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)