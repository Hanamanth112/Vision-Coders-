import asyncio
import datetime
from bson import ObjectId
from database import init_db, get_users_col, get_transactions_col, get_savings_goals_col, get_fraud_alerts_col, hash_password

async def seed_database():
    print("Initializing MongoDB Database Seeding...")
    
    # Initialize connection
    await init_db()
    
    users_col = get_users_col()
    transactions_col = get_transactions_col()
    savings_goals_col = get_savings_goals_col()
    fraud_alerts_col = get_fraud_alerts_col()
    
    # 1. Clean existing collections
    print("Cleaning collections...")
    await users_col.delete_many({})
    await transactions_col.delete_many({})
    await savings_goals_col.delete_many({})
    await fraud_alerts_col.delete_many({})
    
    demo_email = "demo@smartfin.ai"
    
    # 2. Create User
    user_id = str(ObjectId())
    user_doc = {
        "_id": user_id,
        "name": "John Doe",
        "email": demo_email,
        "password_hash": hash_password("demo1234"),
        "monthly_budget": 100000.0,
        "savings_goal": 30000.0,
        "home_location": "New York, USA"
    }
    
    await users_col.insert_one(user_doc)
    print(f"Created Demo User: {user_doc['name']} ({user_doc['email']}) with ID: {user_id}")
    
    # 3. Create default Savings Goal
    deadline_date = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=180)).strftime("%Y-%m-%d")
    goal_doc = {
        "_id": str(ObjectId()),
        "user_id": user_id,
        "name": "Buy Laptop",
        "target_amount": 50000.0,
        "current_amount": 0.0,
        "deadline": deadline_date
    }
    await savings_goals_col.insert_one(goal_doc)
    print(f"Seeded Savings Goal: '{goal_doc['name']}' (Target: INR {goal_doc['target_amount']:,.2f})")
    
    # 4. Create pre-populated transactions
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    
    def relative_date(days_ago, hour):
        d = now - datetime.timedelta(days=days_ago)
        return d.replace(hour=hour, minute=0, second=0, microsecond=0)
        
    default_ip = "67.121.84.19"
    default_dev = "Chrome v124 (Windows 11)"
    
    transactions = [
        # Inflows (Income)
        {
            "user_id": user_id,
            "amount": 150000.00,
            "type": "income",
            "category": "Salary",
            "location": "New York, USA",
            "date": relative_date(20, 9).isoformat(),
            "hour": 9,
            "description": "Salary Credit",
            "ip_address": default_ip,
            "device_fingerprint": default_dev
        },
        {
            "user_id": user_id,
            "amount": 15000.00,
            "type": "income",
            "category": "Investment",
            "location": "New York, USA",
            "date": relative_date(10, 11).isoformat(),
            "hour": 11,
            "description": "Asset Investment Income",
            "ip_address": default_ip,
            "device_fingerprint": default_dev
        },
        # Outflows (Expenses)
        {
            "user_id": user_id,
            "amount": 35000.00,
            "type": "expense",
            "category": "Rent",
            "location": "New York, USA",
            "date": relative_date(24, 10).isoformat(),
            "hour": 10,
            "description": "Apartment Monthly Rent",
            "ip_address": default_ip,
            "device_fingerprint": default_dev
        },
        {
            "user_id": user_id,
            "amount": 8500.00,
            "type": "expense",
            "category": "Groceries",
            "location": "New York, USA",
            "date": relative_date(15, 17).isoformat(),
            "hour": 17,
            "description": "Supermarket Grocery Outflow",
            "ip_address": default_ip,
            "device_fingerprint": default_dev
        },
        {
            "user_id": user_id,
            "amount": 4500.00,
            "type": "expense",
            "category": "Dining Out",
            "location": "New York, USA",
            "date": relative_date(12, 20).isoformat(),
            "hour": 20,
            "description": "Swiggy Food Order",
            "ip_address": default_ip,
            "device_fingerprint": default_dev
        },
        {
            "user_id": user_id,
            "amount": 12000.00,
            "type": "expense",
            "category": "Shopping",
            "location": "New York, USA",
            "date": relative_date(8, 14).isoformat(),
            "hour": 14,
            "description": "Amazon Purchase",
            "ip_address": default_ip,
            "device_fingerprint": default_dev
        },
        {
            "user_id": user_id,
            "amount": 5200.00,
            "type": "expense",
            "category": "Utilities",
            "location": "New York, USA",
            "date": relative_date(5, 11).isoformat(),
            "hour": 11,
            "description": "Monthly Utility Bill Payment",
            "ip_address": default_ip,
            "device_fingerprint": default_dev
        },
        {
            "user_id": user_id,
            "amount": 25000.00,
            "type": "expense",
            "category": "Electronics",
            "location": "New York, USA",
            "date": relative_date(2, 16).isoformat(),
            "hour": 16,
            "description": "Electronics & Gear Purchase",
            "ip_address": default_ip,
            "device_fingerprint": default_dev
        }
    ]
    
    for tx in transactions:
        await transactions_col.insert_one(tx)
        
    print(f"Successfully seeded {len(transactions)} historical transactions with fingerprint logs.")
    print("\nDemo Login Credentials:")
    print("------------------------")
    print(f"Email:    {demo_email}")
    print("Password: demo1234")
    print("------------------------")

if __name__ == "__main__":
    asyncio.run(seed_database())
