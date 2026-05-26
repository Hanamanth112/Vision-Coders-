import os
import joblib
import pandas as pd
import numpy as np

# Risk mapping matching the training script
CATEGORIES_RISK = {
    "Salary": 0.0,
    "Groceries": 0.05,
    "Rent": 0.01,
    "Utilities": 0.02,
    "Dining Out": 0.10,
    "Shopping": 0.20,
    "Electronics": 0.50,
    "Money Transfer": 0.70,
    "Travel": 0.30,
    "Investment": 0.15,
    "Other": 0.10
}

MODEL_PATH = os.path.join(os.path.dirname(__file__), "fraud_model.pkl")
SCALER_PATH = os.path.join(os.path.dirname(__file__), "scaler.pkl")

_model = None
_scaler = None

def load_ml_model():
    global _model, _scaler
    if _model is None or _scaler is None:
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            try:
                _model = joblib.load(MODEL_PATH)
                _scaler = joblib.load(SCALER_PATH)
                print("ML Model and Scaler loaded successfully.")
            except Exception as e:
                print(f"Error loading ML model components: {e}")
        else:
            print("ML Model or Scaler file not found. Please run train_model.py first.")
    return _model, _scaler

def predict_fraud_risk(amount, hour, location_mismatch, velocity, category, description=None):
    """
    Evaluates the transaction features using the user-defined fraud scoring rules:
    - Amount > 50000: +40
    - Velocity (transactions in last hour) > 5: +30
    - Location Mismatch (login_location != usual_location): +35
    - Device Changed / Not registered (implied by Location Mismatch): +25
    - Transaction Hour 1 to 4 AM: +20
    - Blacklisted UPI (description/category contains fraud@upi or scam@ybl): +80
    """
    fraud_score = 0
    details = []
    
    if amount > 50000:
        fraud_score += 40
        details.append("High amount (> ₹50,000)")
        
    if velocity > 5:
        fraud_score += 30
        details.append("High transaction frequency (velocity > 5)")
        
    if location_mismatch:
        # Location mismatch implies login_location != usual_location (+35)
        # and device_not_registered/changed (+25)
        fraud_score += 35
        details.append("Location anomaly (login location != usual location)")
        
        fraud_score += 25
        details.append("Unregistered/Changed device detected")
        
    if hour >= 1 and hour <= 4:
        fraud_score += 20
        details.append("Late night activity (1 AM - 4 AM)")
        
    # Check blacklisted UPI
    blacklisted_upi = ["fraud@upi", "scam@ybl"]
    is_blacklisted = False
    
    # Inspect description or category
    desc_str = (description or "").lower()
    cat_str = (category or "").lower()
    
    for upi in blacklisted_upi:
        if upi in desc_str or upi in cat_str:
            is_blacklisted = True
            break
            
    if is_blacklisted:
        fraud_score += 80
        details.append("Receiver address is blacklisted UPI")
        
    # Determine risk level
    if fraud_score >= 70:
        risk_level = "HIGH"
    elif fraud_score >= 40:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
        
    # Cap the fraud probability and score
    prob = min(0.995, max(0.005, fraud_score / 100.0))
    
    return {
        "fraud_probability": round(prob, 4),
        "risk_score": round(float(fraud_score), 2),
        "risk_level": risk_level,
        "details": "; ".join(details) if details else "Normal parameters",
        "using_fallback": True
    }
