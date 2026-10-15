import sys
from server import app
from core.db import db

def run_tests():
    client = app.test_client()

    print("[TEST 1] Testing unauthenticated redirect on /...")
    r1 = client.get('/', follow_redirects=False)
    assert r1.status_code == 302, f"Expected 302, got {r1.status_code}"
    assert "/login" in r1.headers["Location"], f"Expected redirect to /login, got {r1.headers['Location']}"
    print("  -> PASS: Unauthenticated user redirected to /login")

    print("[TEST 2] Testing unauthenticated 401 on /api/vouchers...")
    r2 = client.get('/api/vouchers')
    assert r2.status_code == 401, f"Expected 401, got {r2.status_code}"
    assert r2.json.get("authenticated") is False
    print("  -> PASS: Unauthenticated API call blocked with 401")

    print("[TEST 3] Testing /login GET page...")
    r3 = client.get('/login')
    assert r3.status_code == 200
    assert b"Admin Authentication" in r3.data
    print("  -> PASS: Login HTML rendered successfully")

    print("[TEST 4] Testing invalid login attempt...")
    r4 = client.post('/api/auth/login', json={"username": "admin", "password": "wrongpassword"})
    assert r4.status_code == 401
    assert r4.json.get("success") is False
    print("  -> PASS: Invalid credentials correctly rejected")

    print("[TEST 5] Testing valid login attempt (admin / admin)...")
    r5 = client.post('/api/auth/login', json={"username": "admin", "password": "admin"})
    assert r5.status_code == 200
    assert r5.json.get("success") is True
    print("  -> PASS: Valid login succeeded")

    print("[TEST 6] Testing authenticated access to / after login...")
    r6 = client.get('/')
    assert r6.status_code == 200
    assert b"SUN BUILDERS PROJECTS LLP" in r6.data
    print("  -> PASS: Authenticated user can access dashboard")

    print("[TEST 7] Testing authenticated access to /api/auth/status...")
    r7 = client.get('/api/auth/status')
    assert r7.status_code == 200
    assert r7.json.get("authenticated") is True
    assert r7.json.get("username") == "admin"
    print("  -> PASS: Session status verified")

    print("[TEST 8] Testing change password to temporary and back...")
    r_chg = client.post('/api/auth/change-password', json={"old_password": "admin", "new_password": "newadmin123"})
    assert r_chg.status_code == 200
    assert r_chg.json.get("success") is True
    # Revert back to admin so it stays admin / admin
    r_rev = client.post('/api/auth/change-password', json={"old_password": "newadmin123", "new_password": "admin"})
    assert r_rev.status_code == 200
    assert r_rev.json.get("success") is True
    print("  -> PASS: Password change and revert verified")

    print("[TEST 9] Testing logout...")
    r8 = client.get('/logout', follow_redirects=False)
    assert r8.status_code == 302
    r9 = client.get('/api/auth/status')
    assert r9.json.get("authenticated") is False
    print("  -> PASS: Logout cleared session successfully")

    print("\n==============================================")
    print(" ALL 9 AUTHENTICATION TESTS PASSED WITH 100%!")
    print("==============================================")

if __name__ == "__main__":
    run_tests()
