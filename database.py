import os
import uuid
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt
from bson import ObjectId

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "smartfin"

client = None
db = None
is_mock = False

# Password Hashing Helpers
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

# --- STATEFUL MOCK MONGODB FOR OUT-OF-THE-BOX EXECUTION ---

class MockCursor:
    def __init__(self, data):
        self.data = list(data)
        
    def sort(self, key, direction=None):
        if isinstance(key, list):
            for k, d in reversed(key):
                self.data.sort(key=lambda x: x.get(k) if x.get(k) is not None else "", reverse=(d == -1))
        else:
            self.data.sort(key=lambda x: x.get(key) if x.get(key) is not None else "", reverse=(direction == -1))
        return self
        
    def limit(self, num):
        self.data = self.data[:num]
        return self
        
    async def to_list(self, length=None):
        if length is not None:
            return self.data[:length]
        return self.data

class MockCollection:
    def __init__(self, name, db_instance):
        self.name = name
        self.db = db_instance
        if name not in self.db._store:
            self.db._store[name] = []
            
    async def find_one(self, query):
        for doc in self.db._store[self.name]:
            if self._matches(doc, query):
                # Return a copy to prevent in-place modification side-effects
                return dict(doc)
        return None
        
    def find(self, query=None):
        query = query or {}
        matches = []
        for doc in self.db._store[self.name]:
            if self._matches(doc, query):
                matches.append(dict(doc))
        return MockCursor(matches)
        
    async def insert_one(self, doc):
        if "_id" not in doc:
            doc["_id"] = str(ObjectId())
        # Store a copy
        self.db._store[self.name].append(dict(doc))
        
        class MockInsertResult:
            inserted_id = doc["_id"]
        return MockInsertResult()
        
    async def update_one(self, query, update):
        # We need to find the document in-place to modify it
        for doc in self.db._store[self.name]:
            if self._matches(doc, query):
                if "$set" in update:
                    for k, v in update["$set"].items():
                        doc[k] = v
                else:
                    for k, v in update.items():
                        doc[k] = v
                class MockUpdateResult:
                    matched_count = 1
                    modified_count = 1
                return MockUpdateResult()
                
        class MockUpdateResult:
            matched_count = 0
            modified_count = 0
        return MockUpdateResult()
        
    async def delete_one(self, query):
        for doc in self.db._store[self.name]:
            if self._matches(doc, query):
                self.db._store[self.name].remove(doc)
                class MockDeleteResult:
                    deleted_count = 1
                return MockDeleteResult()
                
        class MockDeleteResult:
            deleted_count = 0
        return MockDeleteResult()
        
    async def delete_many(self, query):
        removed = 0
        docs_to_remove = []
        for doc in self.db._store[self.name]:
            if self._matches(doc, query):
                docs_to_remove.append(doc)
        for doc in docs_to_remove:
            self.db._store[self.name].remove(doc)
            removed += 1
        class MockDeleteResult:
            deleted_count = removed
        return MockDeleteResult()
        
    async def count_documents(self, query):
        count = 0
        for doc in self.db._store[self.name]:
            if self._matches(doc, query):
                count += 1
        return count

    async def create_index(self, key, unique=False):
        pass

    def _matches(self, doc, query):
        for k, v in query.items():
            # Handle standard nested date ranges or amounts (e.g. {"$gte": val})
            if isinstance(v, dict):
                val = doc.get(k)
                if val is None:
                    return False
                # Convert strings to datetime if comparing
                for op, op_val in v.items():
                    comp_val = val
                    comp_op_val = op_val
                    # Date string vs datetime comparison helper
                    if isinstance(comp_val, str) and isinstance(comp_op_val, datetime.datetime):
                        try:
                            comp_val = datetime.datetime.fromisoformat(comp_val.replace("Z", ""))
                        except ValueError:
                            pass
                    elif isinstance(comp_val, datetime.datetime) and isinstance(comp_op_val, str):
                        try:
                            comp_op_val = datetime.datetime.fromisoformat(comp_op_val.replace("Z", ""))
                        except ValueError:
                            pass
                            
                    if op == "$gte" and not (comp_val >= comp_op_val): return False
                    if op == "$gt" and not (comp_val > comp_op_val): return False
                    if op == "$lte" and not (comp_val <= comp_op_val): return False
                    if op == "$lt" and not (comp_val < comp_op_val): return False
                    if op == "$ne" and not (comp_val != comp_op_val): return False
                    if op == "$in" and not (comp_val in comp_op_val): return False
            elif doc.get(k) != v:
                return False
        return True

class MockDatabase:
    def __init__(self):
        self._store = {}
        self.users = MockCollection("users", self)
        self.transactions = MockCollection("transactions", self)
        self.fraud_alerts = MockCollection("fraud_alerts", self)
        self.savings_goals = MockCollection("savings_goals", self)

    def clear(self):
        self._store.clear()
        self._store["users"] = []
        self._store["transactions"] = []
        self._store["fraud_alerts"] = []
        self._store["savings_goals"] = []

# --- DATABASE LIFE CYCLE MANAGEMENT ---

async def init_db():
    global client, db, is_mock
    
    # Check if mock db is forced via env
    if os.getenv("USE_MOCK_DB", "").lower() == "true":
        print("[MOCK_DB] USE_MOCK_DB is active. Initializing stateful in-memory database simulation...")
        db = MockDatabase()
        is_mock = True
        return

    try:
        # Short timeout (2000ms) to prevent hanging if MongoDB is not running
        client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=2000)
        # Try a quick ping command
        await client.admin.command('ping')
        db = client[DB_NAME]
        is_mock = False
        print(f"[SUCCESS] Successfully connected to MongoDB at: {MONGODB_URI}")
        
        # Ensure unique index on user emails
        await db.users.create_index("email", unique=True)
        # Create other indexes for performance
        await db.transactions.create_index([("user_id", 1), ("date", -1)])
        await db.fraud_alerts.create_index("transaction_id")
        await db.savings_goals.create_index("user_id")
    except Exception as e:
        print(f"[ERROR] MongoDB connection failed: {e}")
        print("[MOCK_DB] Falling back to STATEFUL IN-MEMORY MOCK DATABASE...")
        db = MockDatabase()
        is_mock = True

def get_users_col():
    global db
    if db is None:
        db = MockDatabase()
        is_mock = True
    return db.users

def get_transactions_col():
    global db
    if db is None:
        db = MockDatabase()
        is_mock = True
    return db.transactions

def get_fraud_alerts_col():
    global db
    if db is None:
        db = MockDatabase()
        is_mock = True
    return db.fraud_alerts

def get_savings_goals_col():
    global db
    if db is None:
        db = MockDatabase()
        is_mock = True
    return db.savings_goals
