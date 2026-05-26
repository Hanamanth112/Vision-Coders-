# SmartFin AI - Personal Finance & Cyber Security Fraud Detector

**SmartFin AI** is a state-of-the-art personal finance assistant integrated with real-time cybersecurity fraud detection. Built for hackathons, this application allows users to manage income, budgets, and savings goals while actively protecting their wallets using a real machine learning model trained on transaction behavior anomaly markers.

---

## 🌟 Key Features

### 1. Smart Personal Finance Manager
- **Dynamic Ledger**: Add, edit, delete, and categorize income and expense transactions.
- **Goal & Budget Progress**: Real-time progress trackers calculate monthly budgets and savings metrics.
- **Smart Recommendations Engine**: The backend runs rule-based algorithms to provide customized, human-like insights on saving adjustments (e.g. *"You spent 35% on Dining Out this month. Reducing this will save you $85"*).

### 2. Cybersecurity AI Fraud Defense
- **Real-Time Classification**: Expenses are processed by a real `RandomForestClassifier` trained using Scikit-Learn.
- **Behavioral Feature Analysis**: The model assigns risk probabilities based on:
  - **Transaction Amount**: Extreme amounts compared to category expectations.
  - **Hour of Day**: Suspicious late-night spending spikes (11 PM - 6 AM).
  - **Location Mismatch**: Compares merchant location to user-defined home location.
  - **Transaction Velocity**: Frequency spikes (rapid successions of transactions per hour).
  - **Category Weight**: Custom risk factor associated with merchant type (e.g., Money Transfer vs Groceries).
- **Interactive Security Panel**: Manage flagged items by resolving alerts—either validating them as safe ("Approve Transaction") or confirming threat status ("Flag as Fraud").

---

## 🎨 Premium Dark-Mode User Interface
- **Glassmorphic Cards**: Sleek dark theme (`#070913`) featuring translucent panel backdrops, saturated HSL color guides, and active gradient borders.
- **Floating Aura Animations**: Dynamic floating CSS ambient blobs simulating modern SaaS dashboards.
- **High-fidelity Graphs**: Responsive daily cashflow trend line charts and category doughnut charts powered by Chart.js.
- **Siren Alerts**: Integrates a HTML5 Audio synthesizer context triggering dual-tone warning rings upon detecting a high-probability fraudulent transaction.

---

## ⚙️ Tech Stack & Architecture

- **Frontend**: Single Page Application (HTML5, Custom CSS3, Vanilla JS, Chart.js, Lucide, FontAwesome). *Served statically by Flask to support out-of-the-box local execution without Node.js setup!*
- **Backend**: Python 3 (Flask, SQLAlchemy ORM, Flask-CORS, PyJWT, Joblib).
- **Database**: SQLite (In-process relational DB).
- **AI/ML Model**: Scikit-Learn `RandomForestClassifier` trained on 10,000 synthetic behavioral transaction records.

---

## 🚀 Quick Setup & Execution

Follow these steps to run the complete stack locally:

### 1. Activate the Virtual Environment
Activate the pre-configured local virtual environment:
```powershell
# Windows PowerShell:
.\venv\Scripts\activate
```

### 2. Train the Machine Learning Model
Generate the synthetic database and fit the classifier model. This outputs feature importances and saves the model binary (`fraud_model.pkl` and `scaler.pkl`):
```bash
python backend/train_model.py
```

### 3. Start the Flask Server
Run the Flask server which initializes the SQL schema and starts the local server:
```bash
python backend/app.py
```

### 4. Load the Web Dashboard
Open your browser and navigate to:
**[http://localhost:5000](http://localhost:5000)**

---

## 🔍 Step-by-Step Demo Guide (For Presenting to Judges)

Showcase the full capabilities of **SmartFin AI** in 2 minutes:

1. **Register a New Account**:
   - Register an account with your Name, Email, Monthly Budget (e.g. `$2,000`), and Home Location (e.g. `New York, USA`).
2. **Add a Normal Transaction**:
   - Click **Add Transaction**. Enter: Amount=`$55.00`, Type=`Expense`, Category=`Groceries`, Location=`New York, USA` (matching home location), Date=`Daytime`.
   - *Result*: Added successfully with a green toast. Dashboard balances and charts update. No fraud alerts.
3. **Trigger the AI Fraud Alert**:
   - Click **Add Transaction** again. Add a transaction designed to violate model safety weights:
     - Amount: `$3,500.00`
     - Category: `Money Transfer`
     - Location: `Tokyo, Japan` (Location anomaly mismatch)
     - Time: Set date/time to late night (e.g., `03:45 AM`)
   - *Result*: The system immediately computes high risk. A **RED emergency toast** pops up with a double-tone audio beep, explaining the exact indicators flagged by the Random Forest model!
4. **Inspect the Fraud Center**:
   - Go to the **Fraud Center** tab. Review the transaction parameters and AI explanation logs.
   - Resolve it by clicking **Flag as Fraud** (Dismisses/marks as resolved) or **Approve Transaction** (claims it was user-authorized).
5. **Review AI recommendations**:
   - Return to the **Dashboard Overview**. Observe that the AI recommendations panel shows alerts reflecting your spending behavior and active security warnings!
