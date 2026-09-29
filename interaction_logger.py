"""
interaction_logger.py

InteractionLogger is the write-side counterpart to DataLoader: DataLoader
only reads, this class only writes. Two things get logged, each to its own
file so the original synthetic dataset is never mutated:

  - data/live_interactions.csv : every "attended + rated" action from the
    website gets appended here as a new row.
  - data/live_residents.csv    : every new resident registered through the
    website (a "new guest" who wasn't in the original synthetic dataset)
    gets appended here.

Appending row-by-row with pandas is intentional: it's simple, human-
readable if you open the CSV, and easy to inspect/demo in your video.
"""

import os
from datetime import datetime
import pandas as pd


class InteractionLogger:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.interactions_path = os.path.join(data_dir, "live_interactions.csv")
        self.residents_path = os.path.join(data_dir, "live_residents.csv")

    def log_interaction(self, resident_id, activity_id, attended, rating=None):
        """Appends one interaction row. rating is ignored (stored blank) if attended=False."""
        row = pd.DataFrame([{
            "resident_id": resident_id,
            "activity_id": activity_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "attended": bool(attended),
            "rating": rating if attended else "",
        }])
        file_exists = os.path.exists(self.interactions_path)
        row.to_csv(self.interactions_path, mode="a", header=not file_exists, index=False)

    def register_resident(self, name, interests, mobility_level, preferred_time="no_preference"):
        """
        Registers a brand-new resident (someone not in the original dataset).
        interests: list of tag strings, e.g. ["music", "cards"].
        Returns the new resident_id.
        """
        resident_id = f"GUEST{int(datetime.now().timestamp())}"
        row = pd.DataFrame([{
            "resident_id": resident_id,
            "name": name or "New Resident",
            "age": "",
            "gender": "",
            "mobility_level": mobility_level,
            "interests": ",".join(interests),
            "preferred_time": preferred_time,
            "move_in_date": datetime.now().strftime("%Y-%m-%d"),
        }])
        file_exists = os.path.exists(self.residents_path)
        row.to_csv(self.residents_path, mode="a", header=not file_exists, index=False)
        return resident_id

    def get_recent_interactions(self, n=10):
        """Returns the most recent n logged interactions, for a 'recent activity' feed."""
        if not os.path.exists(self.interactions_path):
            return pd.DataFrame(columns=["resident_id", "activity_id", "date", "attended", "rating"])
        df = pd.read_csv(self.interactions_path)
        return df.tail(n).iloc[::-1]