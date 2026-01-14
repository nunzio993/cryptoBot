"""
CryptoBot API Test Suite
Run with: python tests/test_api.py

Prerequisites:
- Backend running on localhost:8001
- Valid user credentials (admin/admin or your password)
"""
import requests
import time
import sys

BASE_URL = "http://localhost:8001/api"

# Test credentials - CHANGE THESE
USERNAME = "admin"
PASSWORD = "admin123"  # Change to your actual password

# Colors for terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def add(self, name, passed, message=""):
        self.tests.append({"name": name, "passed": passed, "message": message})
        if passed:
            self.passed += 1
            print(f"  [OK] {name}")
        else:
            self.failed += 1
            print(f"  [FAIL] {name}: {message}")
    
    def summary(self):
        print(f"\n{'='*50}")
        print(f"Results: {GREEN}{self.passed} passed{RESET}, {RED}{self.failed} failed{RESET}")
        return self.failed == 0

results = TestResults()
token = None

def login():
    """Login and get JWT token"""
    global token
    print(f"\n{YELLOW}[AUTH TESTS]{RESET}")
    
    # Test 1: Login with correct credentials
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "username": USERNAME,
            "password": PASSWORD
        })
        if resp.status_code == 200:
            data = resp.json()
            if "access_token" in data:
                token = data["access_token"]
                results.add("Login with correct credentials", True)
            elif data.get("requires_2fa"):
                results.add("Login detected 2FA requirement", True)
                print(f"    {YELLOW}⚠ 2FA enabled - skipping some tests{RESET}")
                return False
            else:
                results.add("Login with correct credentials", False, "No token in response")
                return False
        else:
            results.add("Login with correct credentials", False, f"Status {resp.status_code}")
            return False
    except Exception as e:
        results.add("Login with correct credentials", False, str(e))
        return False
    
    # Test 2: Login case-insensitive
    try:
        alt_username = USERNAME.lower() if USERNAME[0].isupper() else USERNAME.capitalize()
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "username": alt_username,
            "password": PASSWORD
        })
        results.add("Login case-insensitive", resp.status_code == 200)
    except Exception as e:
        results.add("Login case-insensitive", False, str(e))
    
    # Test 3: Login with wrong password
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "username": USERNAME,
            "password": "wrongpassword123"
        })
        results.add("Login with wrong password rejected", resp.status_code == 401)
    except Exception as e:
        results.add("Login with wrong password rejected", False, str(e))
    
    return True

def test_health():
    """Test health endpoint"""
    try:
        resp = requests.get(f"{BASE_URL}/health")
        results.add("Health check", resp.status_code == 200)
    except Exception as e:
        results.add("Health check", False, str(e))

def test_api_keys():
    """Test API keys endpoints"""
    print(f"\n{YELLOW}[API KEYS TESTS]{RESET}")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test: List API keys
    try:
        resp = requests.get(f"{BASE_URL}/apikeys", headers=headers)
        results.add("List API keys", resp.status_code == 200)
        keys = resp.json() if resp.status_code == 200 else []
    except Exception as e:
        results.add("List API keys", False, str(e))
        keys = []
    
    return keys

def test_orders(api_key_id=None):
    """Test orders endpoints"""
    print(f"\n{YELLOW}[ORDERS TESTS]{RESET}")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test: List orders
    try:
        params = {"network_mode": "Testnet"}
        if api_key_id:
            params["api_key_id"] = api_key_id
        resp = requests.get(f"{BASE_URL}/orders", headers=headers, params=params)
        results.add("List orders", resp.status_code == 200)
    except Exception as e:
        results.add("List orders", False, str(e))
    
    # Test: Get portfolio (if api_key_id provided)
    if api_key_id:
        try:
            resp = requests.get(
                f"{BASE_URL}/orders/portfolio", 
                headers=headers,
                params={"api_key_id": api_key_id, "network_mode": "Testnet"}
            )
            results.add("Get portfolio", resp.status_code == 200)
            if resp.status_code == 200:
                data = resp.json()
                print(f"    Portfolio: USDC={data.get('usdc_free', 0):.2f}")
        except Exception as e:
            results.add("Get portfolio", False, str(e))

def test_holdings(api_key_id=None):
    """Test holdings endpoints"""
    print(f"\n{YELLOW}[HOLDINGS TESTS]{RESET}")
    headers = {"Authorization": f"Bearer {token}"}
    
    if not api_key_id:
        print(f"    {YELLOW}⚠ Skipped - no API key{RESET}")
        return
    
    try:
        resp = requests.get(
            f"{BASE_URL}/orders/holdings", 
            headers=headers,
            params={"api_key_id": api_key_id}
        )
        results.add("Get holdings", resp.status_code == 200)
        if resp.status_code == 200:
            data = resp.json()
            print(f"    Holdings: {len(data.get('holdings', []))} assets")
    except Exception as e:
        results.add("Get holdings", False, str(e))

def test_websocket():
    """Test WebSocket status endpoint"""
    print(f"\n{YELLOW}[WEBSOCKET TESTS]{RESET}")
    
    try:
        resp = requests.get(f"{BASE_URL[:-4]}/ws/status")  # /ws/status without /api
        results.add("WebSocket status endpoint", resp.status_code == 200)
    except Exception as e:
        results.add("WebSocket status endpoint", False, str(e))

def test_2fa_status():
    """Test 2FA status"""
    print(f"\n{YELLOW}[2FA TESTS]{RESET}")
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(f"{BASE_URL}/2fa/status", headers=headers)
        results.add("2FA status check", resp.status_code == 200)
        if resp.status_code == 200:
            data = resp.json()
            status = "enabled" if data.get("enabled") else "disabled"
            print(f"    2FA Status: {status}")
    except Exception as e:
        results.add("2FA status check", False, str(e))

def test_rate_limiting():
    """Test rate limiting"""
    print(f"\n{YELLOW}[RATE LIMITING TESTS]{RESET}")
    
    # Make multiple rapid requests
    try:
        count = 0
        for i in range(10):
            resp = requests.post(f"{BASE_URL}/auth/login", json={
                "username": "ratelimit_test_user",
                "password": "test"
            })
            if resp.status_code == 429:
                count = i
                break
        
        # Rate limit should kick in before 10 requests
        results.add("Rate limiting active", count > 0 and count < 10)
        if count > 0:
            print(f"    Rate limited after {count} requests")
    except Exception as e:
        results.add("Rate limiting active", False, str(e))

def main():
    print("="*50)
    print("  CryptoBot API Test Suite")
    print("="*50)
    
    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
    except:
        print(f"\n{RED}ERROR: Backend not running on {BASE_URL}{RESET}")
        print("Start it with: .\\start-backend.bat")
        return 1
    
    test_health()
    
    if not login():
        print(f"\n{RED}Login failed - cannot continue tests{RESET}")
        results.summary()
        return 1
    
    # Get API keys for further tests
    keys = test_api_keys()
    api_key_id = keys[0]["id"] if keys else None
    
    if api_key_id:
        print(f"    Using API key ID: {api_key_id}")
    
    test_orders(api_key_id)
    test_holdings(api_key_id)
    test_websocket()
    test_2fa_status()
    # test_rate_limiting()  # Commented to avoid lockout
    
    success = results.summary()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
