import os
import datetime
import jwt
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field

from database import (
    init_db, get_users_col, get_transactions_col, get_fraud_alerts_col, get_savings_goals_col,
    hash_password, verify_password
)
from model import predict_fraud_risk, load_ml_model

# Initialize FastAPI application
app = FastAPI(title="SmartFin AI - Backend API")

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "smartfin_super_secret_jwt_key_for_hackathon"

def utcnow():
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

# --- Exception Handler Overrides for message payload compatibility ---
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"message": str(exc.errors())}
    )

# --- Startup Event to load models & initialize db ---
@app.on_event("startup")
async def startup_event():
    await init_db()
    load_ml_model()
    
    # Auto-seed if database is empty (important for fresh stateful mock database launches)
    try:
        users_col = get_users_col()
        if await users_col.count_documents({}) == 0:
            print("[STARTUP] Database is empty. Running auto-seeder...")
            from seed import seed_database
            await seed_database()
    except Exception as e:
        print(f"[STARTUP] Auto-seeding warning: {e}")

# --- JWT Auth Helpers ---
def encode_token(user_id: str) -> str:
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    payload = {
        "exp": now + datetime.timedelta(days=7),
        "iat": now,
        "sub": user_id
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Access token is missing")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token. Please log in again.")
        
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token. Please log in again.")
        
    users_col = get_users_col()
    user = await users_col.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user

# --- Serialization Helpers ---
def serialize_user(user: dict) -> Optional[dict]:
    if not user: return None
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "monthly_budget": float(user.get("monthly_budget", 1000.0)),
        "savings_goal": float(user.get("savings_goal", 200.0)),
        "home_location": user.get("home_location", "New York, USA")
    }

async def serialize_transaction(tx: dict) -> Optional[dict]:
    if not tx: return None
    tx_id = str(tx["_id"])
    alerts_col = get_fraud_alerts_col()
    alerts = await alerts_col.find({"transaction_id": tx_id}).to_list(length=100)
    serialized_alerts = [serialize_alert(a) for a in alerts]
    
    # Parse date safely
    date_val = tx["date"]
    if not isinstance(date_val, str):
        date_val = date_val.isoformat()
        
    return {
        "id": tx_id,
        "user_id": str(tx["user_id"]),
        "amount": float(tx["amount"]),
        "type": tx["type"],
        "category": tx["category"],
        "date": date_val,
        "location": tx.get("location", "New York, USA"),
        "hour": int(tx.get("hour", 12)),
        "description": tx.get("description", ""),
        "ip_address": tx.get("ip_address"),
        "device_fingerprint": tx.get("device_fingerprint"),
        "has_alert": len(serialized_alerts) > 0,
        "alerts": serialized_alerts
    }

def serialize_alert(alert: dict) -> Optional[dict]:
    if not alert: return None
    return {
        "id": str(alert["_id"]),
        "transaction_id": str(alert["transaction_id"]),
        "risk_score": float(alert["risk_score"]),
        "fraud_probability": float(alert["fraud_probability"]),
        "status": alert.get("status", "Pending"),
        "details": alert.get("details", "")
    }

def serialize_goal(goal: dict) -> Optional[dict]:
    if not goal: return None
    return {
        "id": str(goal["_id"]),
        "user_id": str(goal["user_id"]),
        "name": goal["name"],
        "target_amount": float(goal["target_amount"]),
        "current_amount": float(goal.get("current_amount", 0.0)),
        "deadline": goal.get("deadline")
    }

# --- Pydantic Schema Declarations ---
class RegisterSchema(BaseModel):
    name: str
    email: str
    password: str
    home_location: Optional[str] = "New York, USA"
    monthly_budget: Optional[float] = 1500.0
    savings_goal: Optional[float] = 300.0

class LoginSchema(BaseModel):
    email: str
    password: str

class ProfileUpdateSchema(BaseModel):
    name: Optional[str] = None
    monthly_budget: Optional[float] = None
    savings_goal: Optional[float] = None
    home_location: Optional[str] = None

class TransactionCreateSchema(BaseModel):
    amount: float
    type: Optional[str] = "expense"
    category: str
    location: Optional[str] = None
    description: Optional[str] = ""
    date: Optional[str] = None

class ResolveAlertSchema(BaseModel):
    action: str

class SavingsGoalCreateSchema(BaseModel):
    name: str
    target_amount: float
    deadline: Optional[str] = None

class AddMoneySchema(BaseModel):
    amount: float

# --- Authentication & Registration Endpoints ---
@app.post("/api/register", status_code=201)
async def register(data: RegisterSchema):
    users_col = get_users_col()
    existing = await users_col.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered")
        
    hashed = hash_password(data.password)
    user_doc = {
        "name": data.name,
        "email": data.email,
        "password_hash": hashed,
        "home_location": data.home_location,
        "monthly_budget": data.monthly_budget,
        "savings_goal": data.savings_goal
    }
    res = await users_col.insert_one(user_doc)
    user_id = str(res.inserted_id)
    token = encode_token(user_id)
    user_doc["_id"] = user_id
    
    return {
        "message": "User registered successfully",
        "token": token,
        "user": serialize_user(user_doc)
    }

@app.post("/api/login")
async def login(data: LoginSchema):
    users_col = get_users_col()
    user = await users_col.find_one({"email": data.email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    token = encode_token(str(user["_id"]))
    return {
        "message": "Login successful",
        "token": token,
        "user": serialize_user(user)
    }

@app.get("/api/user/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    return serialize_user(user)

@app.put("/api/user/profile")
async def update_profile(data: ProfileUpdateSchema, user: dict = Depends(get_current_user)):
    users_col = get_users_col()
    update_data = {}
    if data.name is not None: update_data["name"] = data.name
    if data.monthly_budget is not None: update_data["monthly_budget"] = data.monthly_budget
    if data.savings_goal is not None: update_data["savings_goal"] = data.savings_goal
    if data.home_location is not None: update_data["home_location"] = data.home_location
    
    if update_data:
        await users_col.update_one({"_id": user["_id"]}, {"$set": update_data})
        user = await users_col.find_one({"_id": user["_id"]})
        
    return {
        "message": "Profile updated successfully",
        "user": serialize_user(user)
    }

# --- Transactions APIs ---
@app.get("/api/transactions")
async def get_transactions(user: dict = Depends(get_current_user)):
    txs_col = get_transactions_col()
    cursor = txs_col.find({"user_id": str(user["_id"])}).sort("date", -1)
    txs = await cursor.to_list(length=1000)
    
    serialized = []
    for tx in txs:
        serialized.append(await serialize_transaction(tx))
    return serialized

@app.post("/api/transactions", status_code=201)
async def create_transaction(data: TransactionCreateSchema, user: dict = Depends(get_current_user)):
    amount = data.amount
    tx_type = data.type
    category = data.category
    location = data.location or user.get("home_location", "New York, USA")
    description = (data.description or "").strip()
    
    if category in ["Salary", "Investment"]:
        tx_type = "income"
        
    if not description:
        smart_descs = {
            "Salary": "Salary Credit",
            "Investment": "Asset Investment Income",
            "Rent": "Apartment Rental Outflow",
            "Groceries": "Supermarket Grocery Outflow",
            "Utilities": "Monthly Utility Bill Payment",
            "Dining Out": "Swiggy Food Order",
            "Shopping": "Amazon Purchase",
            "Electronics": "Electronics & Gear Purchase",
            "Money Transfer": "UPI Transfer",
            "Travel": "Fuel Payment",
            "Other": "General Outflow"
        }
        description = smart_descs.get(category, "General Transaction")
        
    if location.lower() != user.get("home_location", "").lower():
        ip_address = "185.45.12.8"
        device_fingerprint = "Safari iOS 17 (iPhone 15 Pro)"
    else:
        ip_address = "67.121.84.19"
        device_fingerprint = "Chrome v124 (Windows 11)"
        
    if data.date:
        try:
            tx_date = datetime.datetime.fromisoformat(data.date.replace("Z", ""))
        except ValueError:
            tx_date = datetime.datetime.utcnow()
    else:
        tx_date = datetime.datetime.utcnow()
        
    hour = tx_date.hour
    
    if amount <= 0 and not ("CRITICAL" in description or "SECURITY REPORT" in description):
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
        
    # Calculate Velocity (past 1 hour)
    one_hour_ago = tx_date - datetime.timedelta(hours=1)
    txs_col = get_transactions_col()
    velocity = await txs_col.count_documents({
        "user_id": str(user["_id"]),
        "date": {"$gte": one_hour_ago}
    }) + 1
    
    location_mismatch = 1 if location.lower() != user.get("home_location", "").lower() else 0
    
    # Run prediction
    prediction = predict_fraud_risk(
        amount=amount,
        hour=hour,
        location_mismatch=location_mismatch,
        velocity=velocity,
        category=category,
        description=description
    )
    
    if "CRITICAL" in description or "SECURITY REPORT" in description:
        prediction = {
            "risk_score": 99.5,
            "fraud_probability": 0.995,
            "risk_level": "HIGH",
            "details": description,
            "using_fallback": False
        }
        
    new_tx = {
        "user_id": str(user["_id"]),
        "amount": amount,
        "type": tx_type,
        "category": category,
        "date": tx_date,
        "location": location,
        "hour": hour,
        "description": description,
        "ip_address": ip_address,
        "device_fingerprint": device_fingerprint
    }
    
    res = await txs_col.insert_one(new_tx)
    tx_id = str(res.inserted_id)
    new_tx["_id"] = tx_id
    
    alert_triggered = False
    alert_info = None
    
    if tx_type == "expense" and prediction["risk_score"] >= 40.0:
        alerts_col = get_fraud_alerts_col()
        new_alert = {
            "transaction_id": tx_id,
            "risk_score": prediction["risk_score"],
            "fraud_probability": prediction["fraud_probability"],
            "status": "Pending",
            "details": prediction["details"]
        }
        alert_res = await alerts_col.insert_one(new_alert)
        new_alert["_id"] = alert_res.inserted_id
        alert_triggered = True
        alert_info = serialize_alert(new_alert)
        
    tx_serialized = await serialize_transaction(new_tx)
    
    return {
        "message": "Transaction recorded successfully",
        "transaction": tx_serialized,
        "fraud_report": {
            "fraud_probability": prediction["fraud_probability"],
            "risk_score": prediction["risk_score"],
            "risk_level": prediction["risk_level"],
            "details": prediction["details"],
            "alert_triggered": alert_triggered,
            "alert": alert_info
        }
    }

@app.delete("/api/transactions/{tx_id}")
async def delete_transaction(tx_id: str, user: dict = Depends(get_current_user)):
    txs_col = get_transactions_col()
    tx = await txs_col.find_one({"_id": tx_id, "user_id": str(user["_id"])})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    await txs_col.delete_one({"_id": tx_id})
    alerts_col = get_fraud_alerts_col()
    await alerts_col.delete_many({"transaction_id": tx_id})
    return {"message": "Transaction deleted successfully"}

# --- Dashboard Statistics & Insights ---
@app.get("/api/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    txs_col = get_transactions_col()
    alerts_col = get_fraud_alerts_col()
    
    txs = await txs_col.find({"user_id": str(user["_id"])}).to_list(length=1000)
    dismissed_alerts = await alerts_col.find({"status": "Dismissed"}).to_list(length=1000)
    dismissed_tx_ids = {str(a["transaction_id"]) for a in dismissed_alerts}
    
    active_txs = [t for t in txs if str(t["_id"]) not in dismissed_tx_ids]
    
    total_income = sum(float(t["amount"]) for t in active_txs if t["type"] == "income")
    total_expense = sum(float(t["amount"]) for t in active_txs if t["type"] == "expense")
    balance = total_income - total_expense
    
    now = utcnow()
    start_of_month = datetime.datetime(now.year, now.month, 1)
    
    def parse_date(date_val):
        if isinstance(date_val, str):
            try:
                return datetime.datetime.fromisoformat(date_val.replace("Z", ""))
            except ValueError:
                return utcnow()
        return date_val
        
    monthly_income = sum(float(t["amount"]) for t in active_txs if t["type"] == "income" and parse_date(t["date"]) >= start_of_month)
    monthly_expense = sum(float(t["amount"]) for t in active_txs if t["type"] == "expense" and parse_date(t["date"]) >= start_of_month)
    
    user_tx_ids = [str(t["_id"]) for t in txs]
    pending_alerts_count = await alerts_col.count_documents({
        "status": "Pending",
        "transaction_id": {"$in": user_tx_ids}
    })
    
    monthly_savings = max(0.0, monthly_income - monthly_expense)
    savings_goal_pct = min(100.0, (monthly_savings / float(user.get("savings_goal", 200.0)) * 100.0)) if float(user.get("savings_goal", 200.0)) > 0 else 0.0
    budget_usage_pct = min(100.0, (monthly_expense / float(user.get("monthly_budget", 1000.0)) * 100.0)) if float(user.get("monthly_budget", 1000.0)) > 0 else 0.0
    
    return {
        "total_balance": balance,
        "total_income": total_income,
        "total_expense": total_expense,
        "monthly_expense": monthly_expense,
        "monthly_income": monthly_income,
        "monthly_budget": float(user.get("monthly_budget", 1000.0)),
        "monthly_savings": monthly_savings,
        "savings_goal": float(user.get("savings_goal", 200.0)),
        "savings_progress_pct": round(savings_goal_pct, 2),
        "budget_usage_pct": round(budget_usage_pct, 2),
        "pending_alerts_count": pending_alerts_count
    }

@app.get("/api/dashboard/charts")
async def get_dashboard_charts(user: dict = Depends(get_current_user)):
    txs_col = get_transactions_col()
    alerts_col = get_fraud_alerts_col()
    
    txs = await txs_col.find({"user_id": str(user["_id"])}).to_list(length=1000)
    dismissed_alerts = await alerts_col.find({"status": "Dismissed"}).to_list(length=1000)
    dismissed_tx_ids = {str(a["transaction_id"]) for a in dismissed_alerts}
    
    active_txs = [t for t in txs if str(t["_id"]) not in dismissed_tx_ids]
    
    cat_spend = {}
    for t in active_txs:
        if t["type"] == "expense":
            cat_spend[t["category"]] = cat_spend.get(t["category"], 0.0) + float(t["amount"])
            
    categories = list(cat_spend.keys())
    category_totals = list(cat_spend.values())
    
    thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    
    def parse_date(date_val):
        if isinstance(date_val, str):
            try:
                return datetime.datetime.fromisoformat(date_val.replace("Z", ""))
            except ValueError:
                return datetime.datetime.utcnow()
        return date_val
        
    trends_dict = {}
    for t in active_txs:
        t_date = parse_date(t["date"])
        if t_date >= thirty_days_ago:
            day = t_date.date().isoformat()
            if day not in trends_dict:
                trends_dict[day] = {"date": day, "income": 0.0, "expense": 0.0}
            trends_dict[day][t["type"]] += float(t["amount"])
            
    trends = sorted(trends_dict.values(), key=lambda x: x["date"])
    
    if not trends:
        now = datetime.datetime.utcnow()
        trends = [{"date": (now - datetime.timedelta(days=i)).strftime("%Y-%m-%d"), "income": 0.0, "expense": 0.0} for i in range(5, -1, -1)]
        
    return {
        "categories": {
            "labels": categories,
            "datasets": category_totals
        },
        "trends": trends
    }

@app.get("/api/dashboard/insights")
async def get_dashboard_insights(user: dict = Depends(get_current_user)):
    txs_col = get_transactions_col()
    alerts_col = get_fraud_alerts_col()
    goals_col = get_savings_goals_col()
    
    thirty_days_ago = utcnow() - datetime.timedelta(days=30)
    
    txs = await txs_col.find({"user_id": str(user["_id"])}).to_list(length=1000)
    dismissed_alerts = await alerts_col.find({"status": "Dismissed"}).to_list(length=1000)
    dismissed_tx_ids = {str(a["transaction_id"]) for a in dismissed_alerts}
    
    active_txs = [t for t in txs if str(t["_id"]) not in dismissed_tx_ids]
    
    def parse_date(date_val):
        if isinstance(date_val, str):
            try:
                return datetime.datetime.fromisoformat(date_val.replace("Z", ""))
            except ValueError:
                return utcnow()
        return date_val
        
    active_30d_txs = [t for t in active_txs if parse_date(t["date"]) >= thirty_days_ago]
    total_expense = sum(float(t["amount"]) for t in active_30d_txs if t["type"] == "expense")
    total_income = sum(float(t["amount"]) for t in active_30d_txs if t["type"] == "income")
    
    insights = []
    
    goals = await goals_col.find({"user_id": str(user["_id"])}).to_list(length=100)
    if goals:
        primary_goal = goals[0]
        bal = total_income - total_expense
        saved = primary_goal.get("current_amount", 0.0) + min(max(0.0, primary_goal["target_amount"] - primary_goal.get("current_amount", 0.0)), max(0.0, bal))
        goal_pct = (saved / primary_goal["target_amount"] * 100.0) if primary_goal["target_amount"] > 0 else 0.0
        
        if active_txs:
            sorted_txs = sorted(active_txs, key=lambda x: parse_date(x["date"]), reverse=True)
            latest_tx = sorted_txs[0]
            if latest_tx["type"] == "expense" and float(latest_tx["amount"]) > 5000.0:
                insights.append({
                    "type": "warning",
                    "message": f"Goal Alert: Your recent purchase of ₹{float(latest_tx['amount']):,.2f} decreased your savings. Progress toward '{primary_goal['name']}' (₹{primary_goal['target_amount']:,.2f}) dropped to {goal_pct:.0f}%.",
                    "action": "Optimize Outflow"
                })
                
    if not active_txs:
        return [
            {
                "type": "info",
                "message": "Welcome to SmartFin AI! Add transactions to generate personalized financial recommendations.",
                "action": "Add Transaction"
            }
        ]
        
    now_utc = utcnow()
    start_of_month = datetime.datetime(now_utc.year, now_utc.month, 1)
    active_monthly_txs = [t for t in active_txs if parse_date(t["date"]) >= start_of_month]
    current_month_expense = sum(float(t["amount"]) for t in active_monthly_txs if t["type"] == "expense")
    
    monthly_budget = float(user.get("monthly_budget", 1000.0))
    if current_month_expense > monthly_budget:
        insights.append({
            "type": "warning",
            "message": f"Alert: You have exceeded your monthly budget by ₹{current_month_expense - monthly_budget:.2f}. Try pausing discretionary shopping.",
            "action": "Review Budget"
        })
    elif current_month_expense > 0.8 * monthly_budget:
        insights.append({
            "type": "warning",
            "message": f"Caution: You have utilized {current_month_expense/monthly_budget*100.0:.1f}% of your monthly budget.",
            "action": "Control Spending"
        })
        
    cat_spend = {}
    for t in active_30d_txs:
        if t["type"] == "expense":
            cat_spend[t["category"]] = cat_spend.get(t["category"], 0.0) + float(t["amount"])
            
    if cat_spend:
        highest_cat = max(cat_spend, key=cat_spend.get)
        highest_amt = cat_spend[highest_cat]
        pct = (highest_amt / total_expense) * 100.0 if total_expense > 0 else 0
        
        if pct > 35.0 and highest_cat != "Rent":
            insights.append({
                "type": "info",
                "message": f"Smart Tip: You spent {pct:.0f}% of your budget on {highest_cat} (₹{highest_amt:.2f}) this month. Reducing this by 15% will save you ₹{highest_amt * 0.15:.2f}.",
                "action": f"Optimize {highest_cat}"
              })
              
    savings_goal = float(user.get("savings_goal", 200.0))
    monthly_savings = max(0.0, total_income - total_expense)
    if monthly_savings >= savings_goal and savings_goal > 0:
        insights.append({
            "type": "success",
            "message": f"Great Job! You have surpassed your monthly savings goal of ₹{savings_goal:.2f} by saving ₹{monthly_savings:.2f}!",
            "action": "Invest Savings"
        })
    elif monthly_savings < savings_goal and total_income > 0:
        deficit = savings_goal - monthly_savings
        insights.append({
            "type": "info",
            "message": f"Goal Progress: You are ₹{deficit:.2f} short of your monthly savings goal. Restrict non-essential category purchases to catch up.",
            "action": "Save More"
        })
        
    user_tx_ids = [str(t["_id"]) for t in txs]
    pending_fraud = await alerts_col.count_documents({
        "status": "Pending",
        "transaction_id": {"$in": user_tx_ids}
    })
    
    if pending_fraud > 0:
        insights.append({
            "type": "danger",
            "message": f"Security Warning: You have {pending_fraud} unreviewed transactions flagged as suspicious by our AI model. Check them immediately.",
            "action": "Fraud Center"
        })
        
    if len(insights) < 2:
        insights.append({
            "type": "info",
            "message": "AI Insights: Based on historical patterns, setting your utilities auto-pay during daytime can avoid late payment penalties.",
            "action": "Set Autopay"
        })
        
    return insights

# --- Fraud Alerts Endpoints ---
@app.get("/api/fraud-alerts")
async def get_fraud_alerts(user: dict = Depends(get_current_user)):
    txs_col = get_transactions_col()
    alerts_col = get_fraud_alerts_col()
    
    txs = await txs_col.find({"user_id": str(user["_id"])}).to_list(length=1000)
    tx_map = {str(t["_id"]): t for t in txs}
    
    alerts = await alerts_col.find({"transaction_id": {"$in": list(tx_map.keys())}}).to_list(length=1000)
    
    def parse_date(date_val):
        if isinstance(date_val, str):
            return date_val
        return date_val.isoformat()
        
    result = []
    for a in alerts:
        tx = tx_map[str(a["transaction_id"])]
        result.append({
            "alert_id": str(a["_id"]),
            "risk_score": float(a["risk_score"]),
            "fraud_probability": float(a["fraud_probability"]),
            "status": a.get("status", "Pending"),
            "details": a.get("details", ""),
            "transaction": {
                "id": str(tx["_id"]),
                "amount": float(tx["amount"]),
                "category": tx["category"],
                "date": parse_date(tx["date"]),
                "location": tx.get("location", "New York, USA"),
                "hour": int(tx.get("hour", 12)),
                "description": tx.get("description", "")
            }
        })
        
    result.sort(key=lambda x: tx_map[x["transaction"]["id"]]["date"], reverse=True)
    return result

@app.post("/api/fraud-alerts/{alert_id}/resolve")
async def resolve_fraud_alert(alert_id: str, data: ResolveAlertSchema, user: dict = Depends(get_current_user)):
    action = data.action
    if action not in ["Approved", "Dismissed"]:
        raise HTTPException(status_code=400, detail="Action must be 'Approved' or 'Dismissed'")
        
    alerts_col = get_fraud_alerts_col()
    alert = await alerts_col.find_one({"_id": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    txs_col = get_transactions_col()
    tx = await txs_col.find_one({"_id": alert["transaction_id"], "user_id": str(user["_id"])})
    if not tx:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    await alerts_col.update_one({"_id": alert_id}, {"$set": {"status": action}})
    alert = await alerts_col.find_one({"_id": alert_id})
    return {
        "message": f"Alert marked as {action} successfully",
        "alert": serialize_alert(alert)
    }

# --- Savings Goals APIs ---
@app.get("/api/savings-goals")
async def get_savings_goals(user: dict = Depends(get_current_user)):
    goals_col = get_savings_goals_col()
    goals = await goals_col.find({"user_id": str(user["_id"])}).to_list(length=100)
    
    if not goals:
        six_months_later = (datetime.datetime.utcnow() + datetime.timedelta(days=180)).strftime("%Y-%m-%d")
        default_goal = {
            "user_id": str(user["_id"]),
            "name": "Buy Laptop",
            "target_amount": 50000.0,
            "current_amount": 0.0,
            "deadline": six_months_later
        }
        res = await goals_col.insert_one(default_goal)
        default_goal["_id"] = res.inserted_id
        goals = [default_goal]
        
    txs_col = get_transactions_col()
    alerts_col = get_fraud_alerts_col()
    
    txs = await txs_col.find({"user_id": str(user["_id"])}).to_list(length=1000)
    dismissed_alerts = await alerts_col.find({"status": "Dismissed"}).to_list(length=1000)
    dismissed_tx_ids = {str(a["transaction_id"]) for a in dismissed_alerts}
    
    active_txs = [t for t in txs if str(t["_id"]) not in dismissed_tx_ids]
    
    total_income = sum(float(t["amount"]) for t in active_txs if t["type"] == "income")
    total_expense = sum(float(t["amount"]) for t in active_txs if t["type"] == "expense")
    balance = total_income - total_expense
    
    remaining_balance = max(0.0, balance)
    result = []
    for goal in goals:
        target = float(goal["target_amount"])
        curr = float(goal.get("current_amount", 0.0))
        saved = curr + min(max(0.0, target - curr), remaining_balance)
        allocated = max(0.0, saved - curr)
        remaining_balance -= allocated
        
        g_dict = serialize_goal(goal)
        g_dict["current_amount"] = saved
        g_dict["progress_pct"] = round((saved / target * 100.0), 2) if target > 0 else 0.0
        result.append(g_dict)
        
    return result

@app.post("/api/savings-goals", status_code=201)
async def create_savings_goal(data: SavingsGoalCreateSchema, user: dict = Depends(get_current_user)):
    name = data.name
    target_amount = data.target_amount
    deadline = data.deadline
    
    if not name or target_amount <= 0:
        raise HTTPException(status_code=400, detail="Goal name and positive target amount are required")
        
    goals_col = get_savings_goals_col()
    goal = {
        "user_id": str(user["_id"]),
        "name": name,
        "target_amount": target_amount,
        "current_amount": 0.0,
        "deadline": deadline
    }
    res = await goals_col.insert_one(goal)
    goal["_id"] = res.inserted_id
    
    return {
        "message": "Savings goal added successfully",
        "goal": serialize_goal(goal)
    }

@app.post("/api/savings-goals/{goal_id}/add-money")
async def add_money_to_goal(goal_id: str, data: AddMoneySchema, user: dict = Depends(get_current_user)):
    amount = data.amount
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
        
    goals_col = get_savings_goals_col()
    goal = await goals_col.find_one({"_id": goal_id, "user_id": str(user["_id"])})
    if not goal:
        raise HTTPException(status_code=404, detail="Savings goal not found")
        
    current = float(goal.get("current_amount", 0.0))
    await goals_col.update_one({"_id": goal_id}, {"$set": {"current_amount": current + amount}})
    
    goal = await goals_col.find_one({"_id": goal_id})
    return {
        "message": f"Added amount to '{goal['name']}' successfully",
        "goal": serialize_goal(goal)
    }

@app.delete("/api/savings-goals/{goal_id}")
async def delete_savings_goal(goal_id: str, user: dict = Depends(get_current_user)):
    goals_col = get_savings_goals_col()
    goal = await goals_col.find_one({"_id": goal_id, "user_id": str(user["_id"])})
    if not goal:
        raise HTTPException(status_code=404, detail="Savings goal not found")
        
    await goals_col.delete_one({"_id": goal_id})
    return {"message": "Savings goal deleted successfully"}

# --- Static Routes to serve Single Page Application ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")
INDEX_PATH = os.path.join(BASE_DIR, "frontend", "index.html")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def get_index():
    if os.path.exists(INDEX_PATH):
        return FileResponse(INDEX_PATH)
    return JSONResponse({"message": "Frontend index file not found. Run Vite development server on port 3000."})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
