import os
import random
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score
import joblib

def generate_synthetic_data(num_samples=10000):
    print("Generating synthetic transaction dataset...")
    np.random.seed(42)
    random.seed(42)
    
    # Categories and their custom fraud risk score (0.0 to 1.0)
    categories = {
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
    
    data = []
    
    for _ in range(num_samples):
        # Pick category
        category = random.choice(list(categories.keys()))
        category_risk = categories[category]
        
        # Base attributes
        # Normal transactions typically smaller, salary is large but category risk is 0
        if category == "Salary":
            amount = float(np.random.exponential(scale=2000) + 1000)
            hour = random.randint(8, 17) # Business hours
            location_mismatch = 0
            velocity = 1
        elif category == "Rent":
            amount = float(np.random.normal(loc=1200, scale=100))
            hour = random.randint(7, 22)
            location_mismatch = 0
            velocity = 1
        else:
            # General spending
            amount = float(np.random.exponential(scale=150))
            hour = random.randint(0, 23)
            location_mismatch = 1 if random.random() < 0.08 else 0
            velocity = random.randint(1, 4)
            
        # Let's inject fraud samples with higher probabilities
        # We manually create some anomalies to simulate fraud
        is_fraud_scenario = False
        if random.random() < 0.06: # 6% overall fraud rate
            is_fraud_scenario = True
            category = random.choice(["Electronics", "Money Transfer", "Travel", "Shopping"])
            category_risk = categories[category]
            amount = float(np.random.uniform(800, 7500)) # Large amounts
            hour = random.choice([0, 1, 2, 3, 4, 5, 23]) # Late night hours
            location_mismatch = 1
            velocity = random.randint(3, 7) # Multiple transactions in quick succession
            
        # Calculate a fraud probability score to determine the class
        prob = 0.01
        
        # Risk factors
        if amount > 1000:
            prob += 0.20
        if amount > 3000:
            prob += 0.30
        if hour < 6 or hour > 22:
            prob += 0.15
        if location_mismatch == 1:
            prob += 0.25
        if velocity >= 3:
            prob += 0.15
        prob += category_risk * 0.30
        
        # Add random noise
        prob += random.uniform(-0.1, 0.1)
        prob = max(0.0, min(1.0, prob))
        
        # Determine class based on probability
        # If it was an explicitly injected fraud scenario, force Class = 1
        if is_fraud_scenario or prob > 0.60:
            label = 1
        else:
            label = 0
            
        data.append({
            "amount": amount,
            "hour": hour,
            "location_mismatch": location_mismatch,
            "velocity": velocity,
            "category_risk": category_risk,
            "Class": label
        })
        
    df = pd.DataFrame(data)
    print(f"Dataset generated. Shape: {df.shape}")
    print(f"Class distribution:\n{df['Class'].value_counts(normalize=True)}")
    return df

def train_model():
    df = generate_synthetic_data()
    
    X = df.drop("Class", axis=1)
    y = df["Class"]
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train Random Forest Classifier
    print("Training Random Forest Classifier...")
    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    predictions = model.predict(X_test_scaled)
    acc = accuracy_score(y_test, predictions)
    print(f"Accuracy on Test Set: {acc * 100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, predictions))
    
    # Feature Importances
    importances = model.feature_importances_
    features = X.columns
    print("Feature Importances:")
    for feature, importance in zip(features, importances):
        print(f" - {feature}: {importance:.4f}")
        
    # Save the model and scaler
    os.makedirs("backend", exist_ok=True)
    model_path = os.path.join("backend", "fraud_model.pkl")
    scaler_path = os.path.join("backend", "scaler.pkl")
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    print(f"Model saved to {model_path}")
    print(f"Scaler saved to {scaler_path}")

if __name__ == "__main__":
    train_model()
