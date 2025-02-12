import pymongo
import time

# Connect to MongoDB
mongo_client = pymongo.MongoClient('mongodb+srv://fuckyoudeeply:air8858@cluster0.wroq1fk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
db = mongo_client['voice']
collection = db["users"]

# Get all unique user IDs
user_ids = collection.distinct("user_id")

# User input for update type and duration
update_type = input("Update (P)remium or (T)rial users? ").strip().lower()
while update_type not in ['p', 't']:
    print("Invalid choice. Please enter 'P' for Premium or 'T' for Trial.")
    update_type = input("Update (P)remium or (T)rial users? ").strip().lower()

hours = int(input("Number of hours to add: "))

def is_premium(user_id):
    """Check if a user has active premium status based on time difference"""
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    
    # Skip if no user data or no stored timestamp
    if not user_data or "timestamp" not in user_data:
        return None  # Skip this user
    
    stored_time = user_data["timestamp"]
    time_difference = stored_time - current_time
    
    # Premium if time_difference > 0, else Trial
    return time_difference > 0

# Process updates for all relevant users
for user_id in user_ids:
    prem_status = is_premium(user_id)
    
    # Skip users with no data or no timestamp
    if prem_status is None:
        print(f"Skipping user {user_id} (no data or no timestamp)")
        continue
    
    # Check if user matches the selected type
    if (update_type == 'p' and prem_status) or (update_type == 't' and not prem_status):
        user_data = collection.find_one({"user_id": user_id})
        stored_time = user_data["timestamp"]
        current_time = int(time.time())
        
        if update_type == 'p':
            # For premium users: extend existing time
            new_time = stored_time + (hours * 3600)
        else:
            # For trial users: set new time from current moment
            new_time = current_time + (hours * 3600)
        
        # Update the database
        collection.update_one(
            {"user_id": user_id},
            {"$set": {"timestamp": new_time}},
            upsert=True
        )
        print(f"Updated user {user_id} - new expiration: {time.ctime(new_time)}")
