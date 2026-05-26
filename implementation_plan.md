# Implementation Plan - Migration to FastAPI, React, and MongoDB

This plan outlines the steps to migrate the **SmartFin AI** application from a Flask/SQLite/VanillaJS single-page architecture to a modern, secure stack:
- **Frontend**: React (Vite, TypeScript, Tailwind/Custom CSS, Lucide icons, Chart.js)
- **Backend**: FastAPI (Python 3, Asynchronous database queries, JWT authentication)
- **Database**: MongoDB (using Motor async driver)
- **Security & AI**: Pre-trained Random Forest Classifier for fraud classification + Custom heuristics + SOS warning triggers + 2FA Mock OTP

---

## User Review Required

> [!IMPORTANT]
> **Database Fallback Mechanism**: To ensure the application runs instantly without requiring the user to have a running MongoDB local/cloud server, we will implement an **automatic mock fallback**. If connection to MongoDB fails or `USE_MOCK_DB=true` is set, the database helper will switch to a stateful in-memory database simulation (simulating all Mongo query methods). This ensures the app is 100% testable out-of-the-box.
> 
> **CSS & Theme Style**: We will adapt the existing premium dark-mode, glassmorphic custom CSS (`style.css`) to the React app to preserve the stunning aesthetics, responsive CSS grids, and ambient floating glows.

---

## Open Questions

- **MongoDB Instance**: Do you have a local MongoDB running, or should we default to a standard connection string (e.g. `mongodb://localhost:27017/smartfin`) and rely on the automatic mock fallback if it's not detected?
  * *Proposed action*: We will configure it to connect to `mongodb://localhost:27017/smartfin` by default, customizable via a `MONGODB_URI` environment variable, and automatically fall back to the stateful mock database if the server is unreachable.

---

## Proposed Changes

We will restructure the project to keep the backend and frontend cleanly separated:
- `backend/`: Will contain the FastAPI routes, MongoDB database models, seed scripts, and the ML fraud detection model.
- `frontend/`: Will be recreated as a Vite + React + TypeScript application.

### [1. FastAPI Backend]

We will migrate the Flask API to FastAPI. The backend will serve the endpoints asynchronously using `motor.motor_asyncio`.

#### [MODIFY] [requirements.txt](file:///c:/Users/sande/OneDrive/Documents/Fintech/backend/requirements.txt)
Update python requirements to include FastAPI, Uvicorn, Motor (MongoDB driver), Pymongo, PyJWT, and bcrypt.

#### [NEW] [database.py](file:///c:/Users/sande/OneDrive/Documents/Fintech/backend/database.py)
Rewrite database operations to connect to MongoDB/Mock MongoDB. Create a global `db` client, define helper collections, and initialize default user records.

#### [MODIFY] [app.py](file:///c:/Users/sande/OneDrive/Documents/Fintech/backend/app.py)
Rewrite Flask web app as a FastAPI web app with standard JWT authentication dependencies (`get_current_user`), CORS middlewares, and matching routes for transactions, stats, insights, goals, and fraud alerts.

#### [MODIFY] [seed.py](file:///c:/Users/sande/OneDrive/Documents/Fintech/backend/seed.py)
Rewrite the database seed script to work with MongoDB and populate mock data for a clean demonstration.

#### [MODIFY] [test_api.py](file:///c:/Users/sande/OneDrive/Documents/Fintech/backend/test_api.py)
Update test suite to run API tests against the FastAPI app utilizing the in-memory database driver.

---

### [2. React Frontend]

We will replace the Vanilla JS application with a modular React + TypeScript application.

#### [NEW] [frontend/package.json](file:///c:/Users/sande/OneDrive/Documents/Fintech/frontend/package.json)
Initialize standard React & TypeScript package file with Vite, Lucide-React, Chart.js, and React-Chartjs-2.

#### [NEW] [frontend/index.html](file:///c:/Users/sande/OneDrive/Documents/Fintech/frontend/index.html)
Vite-compatible entrypoint HTML including Google Fonts.

#### [NEW] [frontend/src/](file:///c:/Users/sande/OneDrive/Documents/Fintech/frontend/src)
Create modular React components:
- `src/App.tsx`: Main route controller, holds global states (auth, active tab, notification toasts).
- `src/components/`:
  - `Auth.tsx`: Renders Login, Signup, and OTP forms.
  - `Sidebar.tsx`: Sidebar navigation, profile, theme controls, and logout.
  - `Metrics.tsx`: Numeric financial cards with progress bar limits.
  - `Charts.tsx`: Daily Cashflow (Line/Area) and Category breakdown (Doughnut) charts.
  - `TransactionsList.tsx`: Complete ledger with query filters, searches, and CSV export.
  - `FraudCenter.tsx`: Handles fraud alerts management, sandbox simulators, features importances, and the emergency SOS system.
  - `Settings.tsx`: Targets, budget constraints, profile details, and goal creation.
  - `Modals.tsx`: Unified overlays for adding transactions, contributing to goals, and critical fraud sirens.

---

## Verification Plan

### Automated Tests
- Run updated API unit tests:
  ```powershell
  python -m unittest backend/test_api.py
  ```
- Validate React frontend builds correctly:
  ```bash
  cd frontend
  npm run build
  ```

### Manual Verification
1. **Startup Verification**: Run `python backend/app.py` to start the FastAPI server on port 5000, checking the console logs to see if it successfully connects to MongoDB or falls back to Mock DB.
2. **Launch React**: Run `npm run dev` in `frontend` and open the web dashboard.
3. **Register/Login**: Register a new user and log in. Verify 2FA OTP screens trigger correctly.
4. **Transaction Logging**: Log normal and suspicious transactions, verifying that the Scikit-Learn/rule-based scoring tags high-risk cases and triggers audio/visual sirens.
5. **Insights & Budgets**: Modify settings, create savings goals, add contributions, and check if AI recommendations update in real-time.
