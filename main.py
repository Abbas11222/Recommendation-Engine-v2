"""
main.py

Entry point. Wires together every component in dependency order:

    DataLoader
        |
        v
  ContentRecommender   CollaborativeRecommender
        \\                 /
         v               v
            HybridEngine
                |
                v
        Ranked recommendations
                |
                v
            Evaluator (stress test)

Run with: python main.py
"""

from data_loader import DataLoader
from content_recommender import ContentRecommender
from collaborative_recommander import CollaborativeRecommender
from hybrid_engine import HybridEngine
from evaluator import Evaluator


def print_recommendations(resident_row, recs, engine):
    print(f"\nRecommendations for {resident_row['name']} ({resident_row['resident_id']})")
    print(f"  Interests: {resident_row['interests']}")
    print(f"  Mobility:  {resident_row['mobility_level']}")
    print("-" * 60)
    for _, row in recs.iterrows():
        print(f"  {row['name']:<28} score={row['hybrid_score']:.2f}  "
              f"[{row['source']}]")
        print(f"    -> {engine.explain(row)}")


def main():
    # 1. Load data
    loader = DataLoader(data_dir="data").load_all()

    # 2. Fit both recommenders
    content = ContentRecommender().fit(loader.activities_df)
    collaborative = CollaborativeRecommender().fit(loader.interactions_df)

    # 3. Build the hybrid engine (equal weight to start -- tune later)
    engine = HybridEngine(content, collaborative, content_weight=0.5, collab_weight=0.5)

    # 4. Get recommendations for a few real residents
    for resident_id in ["R001", "R010", "R025"]:
        resident_row = loader.get_resident(resident_id)
        history_ids = set(loader.get_resident_history(resident_id)["activity_id"])
        recs = engine.recommend(resident_row, history_ids, n=5)
        print_recommendations(resident_row, recs, engine)

    # 5. Run the required evaluation/testing suite
    print("\n")
    evaluator = Evaluator(engine, loader)
    evaluator.run_all()


if __name__ == "__main__":
    main()