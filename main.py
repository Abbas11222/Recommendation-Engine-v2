from data_loader import DataLoader


load = DataLoader("data")

activities,residents,interactions = load.load_all()


print(f"activities are {activities.head()} , \n residents are {residents.tail()} , \n interactions are {interactions.sample(5)}")


