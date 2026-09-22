"""
generate_dataset.py

Generates a synthetic but realistic dataset for the Elderly Care Facility
Recommendation Engine (Week 3 project).

WHY SYNTHETIC DATA:
Real resident activity/preference data is private (health-adjacent personal
data) and not publicly available, and no real facility dataset exists for
this project. Generating a script-based synthetic dataset is the standard
approach in this situation: it is reproducible, realistic in structure, and
lets us build/test the recommender logic before any real data exists.

OUTPUT FILES (data/):
  - residents.csv      : resident profiles
  - activities.csv      : activity/program catalog
  - interactions.csv    : who attended what, and their rating

Run with: python generate_dataset.py
"""

import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

# ---------------------------------------------------------------------------
# 1. ACTIVITIES CATALOG
# ---------------------------------------------------------------------------
# Categories researched from how real senior/independent-living facilities
# typically structure their activity calendars (fitness, arts, social,
# music, cognitive/educational, outdoor, spiritual, culinary).

activities_raw = [
    # (name, category, tags, physical_intensity, group_size, duration_min)
    ("Chair Yoga", "Fitness & Movement", "yoga,stretching,low-impact", "low", "small", 45),
    ("Morning Tai Chi", "Fitness & Movement", "tai-chi,balance,mindfulness", "low", "medium", 30),
    ("Walking Club", "Fitness & Movement", "walking,cardio,outdoor", "medium", "small", 40),
    ("Seated Strength Training", "Fitness & Movement", "strength,resistance-bands,low-impact", "low", "small", 30),
    ("Water Aerobics", "Fitness & Movement", "swimming,cardio,low-impact", "medium", "medium", 45),
    ("Dance for Fun", "Fitness & Movement", "dance,music,cardio", "medium", "large", 40),
    ("Watercolor Painting", "Arts & Crafts", "painting,creative,fine-motor", "low", "small", 60),
    ("Pottery Workshop", "Arts & Crafts", "pottery,creative,fine-motor", "low", "small", 60),
    ("Knitting Circle", "Arts & Crafts", "knitting,social,fine-motor", "low", "small", 60),
    ("Scrapbooking Club", "Arts & Crafts", "scrapbooking,memory,creative", "low", "small", 50),
    ("Woodworking Basics", "Arts & Crafts", "woodworking,creative,hands-on", "medium", "small", 60),
    ("Bingo Night", "Social & Games", "bingo,social,games", "low", "large", 60),
    ("Card Games Club", "Social & Games", "cards,strategy,social", "low", "small", 60),
    ("Trivia Afternoon", "Social & Games", "trivia,cognitive,social", "low", "medium", 45),
    ("Board Game Social", "Social & Games", "board-games,strategy,social", "low", "medium", 60),
    ("Billiards Club", "Social & Games", "billiards,social,hand-eye", "low", "small", 45),
    ("Live Piano Hour", "Music & Entertainment", "music,piano,listening", "low", "large", 45),
    ("Sing-Along Session", "Music & Entertainment", "music,singing,social", "low", "large", 40),
    ("Movie Afternoon", "Music & Entertainment", "movies,relaxation,social", "low", "large", 90),
    ("Karaoke Fun", "Music & Entertainment", "music,singing,social", "low", "medium", 60),
    ("Book Club", "Educational & Cognitive", "reading,discussion,cognitive", "low", "small", 60),
    ("Current Events Discussion", "Educational & Cognitive", "discussion,news,cognitive", "low", "medium", 45),
    ("Memory & Brain Games", "Educational & Cognitive", "puzzles,memory,cognitive", "low", "small", 30),
    ("Language Learning Circle", "Educational & Cognitive", "language,learning,cognitive", "low", "small", 45),
    ("History Lecture Series", "Educational & Cognitive", "history,lecture,cognitive", "low", "medium", 50),
    ("Garden Club", "Outdoor & Nature", "gardening,outdoor,hands-on", "medium", "small", 60),
    ("Bird Watching Walk", "Outdoor & Nature", "nature,walking,outdoor", "low", "small", 45),
    ("Outdoor Courtyard Social", "Outdoor & Nature", "social,outdoor,relaxation", "low", "medium", 45),
    ("Meditation & Mindfulness", "Spiritual & Reflection", "meditation,mindfulness,relaxation", "low", "small", 30),
    ("Sunday Fellowship Circle", "Spiritual & Reflection", "spiritual,community,reflection", "low", "medium", 45),
    ("Baking Club", "Culinary", "baking,hands-on,social", "low", "small", 60),
    ("Cooking Demo", "Culinary", "cooking,demo,social", "low", "medium", 45),
    ("Tea Tasting Social", "Culinary", "tea,social,relaxation", "low", "small", 30),
]

activities = pd.DataFrame(activities_raw, columns=[
    "name", "category", "tags", "physical_intensity", "group_size", "duration_min"
])
activities.insert(0, "activity_id", ["A" + str(i + 1).zfill(3) for i in range(len(activities))])

# ---------------------------------------------------------------------------
# 2. RESIDENTS
# ---------------------------------------------------------------------------
first_names = ["Margaret","Robert","Dorothy","William","Betty","James","Helen","John",
    "Ruth","Charles","Patricia","George","Nancy","Frank","Carol","Edward","Joan",
    "Richard","Barbara","Harold","Shirley","Donald","Joyce","Kenneth","Doris",
    "Paul","Norma","Raymond","Marilyn","Arthur","Gloria","Walter","Rose","Eugene",
    "Frances","Albert","Evelyn","Ralph","Jean","Gerald","Alice","Roy","Marie",
    "Clarence","Florence","Herbert","Lois","Leonard","Anna","Vernon"]
last_names = ["Smith","Johnson","Williams","Brown","Jones","Miller","Davis","Garcia",
    "Rodriguez","Wilson","Martinez","Anderson","Taylor","Thomas","Moore","Jackson",
    "Martin","Lee","Perez","Thompson","White","Harris","Clark","Lewis","Robinson",
    "Walker","Young","Allen","King","Wright","Scott","Torres","Hill","Green",
    "Adams","Baker","Nelson","Carter","Mitchell","Roberts"]

mobility_levels = ["independent", "uses_cane", "uses_walker", "wheelchair"]
mobility_weights = [0.45, 0.25, 0.20, 0.10]
time_prefs = ["morning", "afternoon", "evening", "no_preference"]
time_weights = [0.35, 0.35, 0.10, 0.20]

# interest tags drawn from the same vocabulary used in activity tags,
# so content-based similarity has real overlap to work with
interest_pool = ["yoga","stretching","tai-chi","balance","walking","cardio",
    "strength","painting","creative","pottery","knitting","scrapbooking",
    "woodworking","bingo","cards","trivia","board-games","billiards","music",
    "piano","singing","movies","reading","discussion","puzzles","memory",
    "language","history","gardening","nature","meditation","mindfulness",
    "spiritual","baking","cooking","tea","social","relaxation"]

N_RESIDENTS = 45
residents = []
used_names = set()
for i in range(N_RESIDENTS):
    while True:
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        if name not in used_names:
            used_names.add(name)
            break
    age = int(np.clip(np.random.normal(80, 6), 65, 98))
    mobility = np.random.choice(mobility_levels, p=mobility_weights)
    n_interests = random.randint(3, 6)
    interests = sorted(random.sample(interest_pool, n_interests))
    preferred_time = np.random.choice(time_prefs, p=time_weights)
    move_in_date = (datetime(2023, 1, 1) + timedelta(days=random.randint(0, 900))).strftime("%Y-%m-%d")
    residents.append({
        "resident_id": f"R{str(i+1).zfill(3)}",
        "name": name,
        "age": age,
        "mobility_level": mobility,
        "interests": ",".join(interests),
        "preferred_time": preferred_time,
        "move_in_date": move_in_date,
    })

residents = pd.DataFrame(residents)

# ---------------------------------------------------------------------------
# 3. INTERACTIONS (attendance + ratings)
# ---------------------------------------------------------------------------
# Logic: a resident is MORE likely to attend & rate highly an activity whose
# tags overlap with their stated interests (this creates realistic signal
# for both content-based AND collaborative filtering to detect), plus some
# random noise so it isn't a perfectly clean pattern (real behavior is messy).

def tag_overlap_score(resident_interests, activity_tags):
    r = set(resident_interests.split(","))
    a = set(activity_tags.split(","))
    return len(r & a)

interactions = []
today = datetime(2025, 9, 1)

for _, res in residents.iterrows():
    # each resident has tried somewhere between 6 and 16 activities
    n_tried = random.randint(6, 16)
    # weight activity selection toward overlapping interests, but allow exploration
    weights = []
    for _, act in activities.iterrows():
        overlap = tag_overlap_score(res["interests"], act["tags"])
        weights.append(1 + overlap * 3)  # baseline chance + boost for overlap
    weights = np.array(weights, dtype=float)
    weights /= weights.sum()

    chosen_idx = np.random.choice(activities.index, size=n_tried, replace=False, p=weights)

    for idx in chosen_idx:
        act = activities.loc[idx]
        overlap = tag_overlap_score(res["interests"], act["tags"])
        attended = random.random() < min(0.6 + overlap * 0.1, 0.95)

        rating = None
        if attended:
            # higher overlap -> higher expected rating, with noise
            base = 3.0 + overlap * 0.6
            rating = int(np.clip(round(np.random.normal(base, 0.8)), 1, 5))

        interaction_date = (today - timedelta(days=random.randint(1, 365))).strftime("%Y-%m-%d")

        interactions.append({
            "resident_id": res["resident_id"],
            "activity_id": act["activity_id"],
            "date": interaction_date,
            "attended": attended,
            "rating": rating if attended else "",
        })

interactions = pd.DataFrame(interactions)

# ---------------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------------
activities.to_csv("data/activities.csv", index=False)
residents.to_csv("data/residents.csv", index=False)
interactions.to_csv("data/interactions.csv", index=False)

print(f"activities.csv   -> {len(activities)} rows")
print(f"residents.csv    -> {len(residents)} rows")
print(f"interactions.csv -> {len(interactions)} rows")
print("\nSample residents:")
print(residents.head(3).to_string(index=False))
print("\nSample activities:")
print(activities.head(3).to_string(index=False))
print("\nSample interactions:")
print(interactions.head(5).to_string(index=False))