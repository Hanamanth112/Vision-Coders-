import os
import unittest
import asyncio
import datetime
from fastapi.testclient import TestClient

# Set environment variable to force Mock DB before importing database/app
os.environ["USE_MOCK_DB"] = "true"

from app import app, SECRET_KEY
import database

class SmartFinTestCase(unittest.TestCase):
    def setUp(self):
        # Force DB initialization
        asyncio.run(database.init_db())
        self.client = TestClient(app)
        
        # Reset the mock store for a clean test environment
        if database.db is not None and database.is_mock:
            database.db.clear()
            
        # Test User details
        self.test_user = {
            "name": "Alex Mercer",
            "email": "alex@mercer.com",
            "password": "Password123",
            "home_location": "London, UK",
            "monthly_budget": 2000.0,
            "savings_goal": 500.0
        }
        
    def register_user(self):
        return self.client.post(
            '/api/register',
            json=self.test_user
        )

    def login_user(self):
        # First register
        self.register_user()
        # Then login
        return self.client.post(
            '/api/login',
            json={
                "email": self.test_user["email"],
                "password": self.test_user["password"]
            }
        )

    def test_registration(self):
        res = self.register_user()
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("token", data)
        self.assertEqual(data["user"]["email"], self.test_user["email"])
        self.assertEqual(data["user"]["name"], self.test_user["name"])

    def test_login(self):
        res = self.login_user()
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("token", data)
        self.assertEqual(data["user"]["email"], self.test_user["email"])

    def test_invalid_login(self):
        self.register_user()
        res = self.client.post(
            '/api/login',
            json={
                "email": self.test_user["email"],
                "password": "WrongPassword"
            }
        )
        self.assertEqual(res.status_code, 401)

    def test_add_normal_transaction(self):
        login_res = self.login_user()
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Post a normal daytime transaction in the home location
        tx_data = {
            "amount": 45.50,
            "type": "expense",
            "category": "Groceries",
            "location": "London, UK", # Matches home location
            "date": "2026-05-25T14:30:00Z", # Daytime hour (14:30)
            "description": "Weekly grocery run"
        }
        
        res = self.client.post(
            '/api/transactions',
            json=tx_data,
            headers=headers
        )
        
        self.assertEqual(res.status_code, 201, f"Expected 201, got {res.status_code}: {res.text}")
        data = res.json()
        self.assertEqual(data["transaction"]["amount"], 45.50)
        self.assertFalse(data["fraud_report"]["alert_triggered"])
        self.assertEqual(data["fraud_report"]["risk_level"], "LOW")

    def test_add_suspicious_transaction(self):
        login_res = self.login_user()
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Post a suspicious transaction: high amount, location anomaly, late-night hours
        tx_data = {
            "amount": 4800.00, # High amount
            "type": "expense",
            "category": "Money Transfer", # High risk category
            "location": "Tokyo, Japan", # Location mismatch
            "date": "2026-05-25T03:15:00Z", # Late night hour (03:15)
            "description": "External wire transfer"
        }
        
        res = self.client.post(
            '/api/transactions',
            json=tx_data,
            headers=headers
        )
        
        self.assertEqual(res.status_code, 201, f"Expected 201, got {res.status_code}: {res.text}")
        data = res.json()
        
        # The AI model / heuristics should flag this transaction
        self.assertTrue(data["fraud_report"]["alert_triggered"])
        self.assertIn(data["fraud_report"]["risk_level"], ["MEDIUM", "HIGH"])
        self.assertIsNotNone(data["fraud_report"]["alert"])
        self.assertEqual(data["fraud_report"]["alert"]["status"], "Pending")

    def test_dashboard_stats_and_insights(self):
        login_res = self.login_user()
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Add normal income
        self.client.post(
            '/api/transactions',
            json={
                "amount": 3000.00,
                "type": "income",
                "category": "Salary",
                "location": "London, UK",
                "date": "2026-05-01T09:00:00Z",
                "description": "Monthly paycheck"
            },
            headers=headers
        )
        
        # Add normal expense
        self.client.post(
            '/api/transactions',
            json={
                "amount": 500.00,
                "type": "expense",
                "category": "Rent",
                "location": "London, UK",
                "date": "2026-05-02T12:00:00Z",
                "description": "Rent payment"
            },
            headers=headers
        )

        # Get Stats
        stats_res = self.client.get('/api/dashboard/stats', headers=headers)
        self.assertEqual(stats_res.status_code, 200, f"Expected 200, got {stats_res.status_code}: {stats_res.text}")
        stats = stats_res.json()
        self.assertEqual(stats["total_balance"], 2500.00)
        self.assertEqual(stats["total_income"], 3000.00)
        self.assertEqual(stats["total_expense"], 500.00)
        
        # Get AI insights
        insights_res = self.client.get('/api/dashboard/insights', headers=headers)
        self.assertEqual(insights_res.status_code, 200)
        insights = insights_res.json()
        self.assertTrue(len(insights) > 0)

if __name__ == '__main__':
    unittest.main()
