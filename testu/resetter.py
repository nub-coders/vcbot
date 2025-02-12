import pymongo
import time
import os
mongo_client  = pymongo.MongoClient('mongodb+srv://fuckyoudeeply:air8858@cluster0.wroq1fk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
db = mongo_client['voice']  # Replace 'your_database_name' with your actual database name
collection = db["users"]

user_ids = collection.distinct("user_id")
days = int(input("No of days: "))
def is_premium(user_id):
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    if user_data:
        stored_time = user_data.get("timestamp")
        if not stored_time:
          return True
        time_difference =  stored_time - current_time
        print(time_difference)
        if time_difference > 0:
            return True
        return False
    return True
for user_id in user_ids:
    prem = is_premium(user_id)
    timestamp = int(time.time()) + (days  * 60 * 60)
    if not prem:
        #user_data = {"user_id": user_id, "timestamp": timestamp}
        #collection.update_one({"user_id": user_id}, {"$unset": {"timestamp": ''}}, upsert=True)
        collection.update_one(
        {"user_id": user_id},
        {"$set": {"timestamp": timestamp}},
        upsert=True
    )
        #collection.replace_one({"user_id": user_id}, user_data, upsert=True)
