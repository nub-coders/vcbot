import pymongo
import time
import os
mongo_client  = pymongo.MongoClient('mongodb+srv://fuckyoudeeply:air8858@cluster0.wroq1fk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
def storre_user(user_id, timestamp, collection):
    """
    Stores or updates user data with a timestamp in MongoDB using update_one.

    Args:
        user_id (int): The ID of the user.
        timestamp (int): The timestamp to store.
        collection (pymongo.collection.Collection): The MongoDB collection.
    """
    collection.update_one(
        {"user_id": user_id},
        {"$set": {"timestamp": timestamp}},
        upsert=True
    )

def main():

    db = mongo_client['voice']  # Replace 'your_database_name' with your actual database name
    collection = db["users"]

    print("Connected to MongoDB successfully!")

    while True:
        try:
            user_id = int(input("Enter user ID (or type 'exit' to quit): "))
            user_data = collection.find_one({"user_id": user_id})

            if user_id == "exit":
               break
            if not user_data:
               print("data not found")
               continue
            no_of_days = int(input("Enter the number of days: "))

            timestamp = int(time.time()) + (no_of_days * 24 * 60 * 60)

            storre_user(user_id, timestamp, collection)
            print(f"Timestamp set for user {user_id} to {no_of_days}")

        except ValueError:
            print("Invalid input. Please enter a valid integer for user ID and number of days.")
        except Exception as e:
            print(f"An error occurred: {e}")
    print("Program terminated")
    mongo_client.close() # Close connection to mongo


if __name__ == "__main__":
    main()
