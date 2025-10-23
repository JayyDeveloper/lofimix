#!/usr/bin/env python3
"""
Diagnostic script to check why YouTube routes aren't loading.
Run this: python3 diagnose.py
"""

import sys
import os

print("=" * 60)
print("LOFIMIX YOUTUBE DIAGNOSTIC TOOL")
print("=" * 60)

# Check 1: Are we in the right directory?
print("\n[1] Checking directory...")
if os.path.exists('app.py'):
    print("    ✓ app.py found")
else:
    print("    ✗ app.py NOT found!")
    print("    Run this from the lofimix directory")
    sys.exit(1)

# Check 2: Does app.py have the YouTube routes?
print("\n[2] Checking if YouTube routes exist in app.py...")
with open('app.py', 'r') as f:
    content = f.read()

routes_to_check = [
    ("/youtube/auth", "YouTube auth route"),
    ("/oauth2callback", "OAuth callback route"),
    ("/youtube/status", "YouTube status route"),
    ("def youtube_auth", "youtube_auth function"),
    ("def youtube_callback", "youtube_callback function"),
]

missing_routes = []
for route, desc in routes_to_check:
    if route in content:
        print(f"    ✓ {desc}")
    else:
        print(f"    ✗ {desc} NOT FOUND!")
        missing_routes.append(desc)

if missing_routes:
    print("\n    ⚠️  PROBLEM: Routes are missing from app.py!")
    print("    Your code is out of date. Run:")
    print("    git pull origin claude/code-review-011CUP12EDoDPHQT1Khn8Les")
    sys.exit(1)

# Check 3: Check YOUTUBE_ENABLED logic
print("\n[3] Checking YOUTUBE_ENABLED logic...")
if "YOUTUBE_ENABLED = False" in content:
    print("    Found: YOUTUBE_ENABLED = False")
if "YOUTUBE_ENABLED = os.path.exists('youtube_config.json')" in content:
    print("    Found: YOUTUBE_ENABLED = os.path.exists('youtube_config.json')")
    if os.path.exists('youtube_config.json'):
        print("    ✓ youtube_config.json exists")
    else:
        print("    ✗ youtube_config.json NOT found!")
        print("    Create this file to enable YouTube features")

# Check 4: Try importing the app
print("\n[4] Attempting to import app...")
try:
    import app as app_module
    print("    ✓ App imported successfully")

    # Check YOUTUBE_ENABLED value
    print(f"    YOUTUBE_ENABLED = {app_module.YOUTUBE_ENABLED}")

    # List all routes
    print("\n[5] Checking registered routes...")
    all_routes = list(app_module.app.url_map.iter_rules())
    youtube_routes = [r for r in all_routes if 'youtube' in str(r.rule).lower() or 'oauth' in str(r.rule).lower()]

    if youtube_routes:
        print(f"    ✓ Found {len(youtube_routes)} YouTube/OAuth routes:")
        for route in youtube_routes:
            print(f"      - {route.rule}")
    else:
        print("    ✗ NO YouTube/OAuth routes registered!")
        print("\n    DIAGNOSIS:")
        if not app_module.YOUTUBE_ENABLED:
            print("    • YOUTUBE_ENABLED is False")
            print("    • Routes are only registered if YOUTUBE_ENABLED is True")
            print("    • Make sure youtube_config.json exists")
        else:
            print("    • YOUTUBE_ENABLED is True but routes didn't load")
            print("    • This might be an import error")

    print(f"\n    Total routes registered: {len(all_routes)}")

except ImportError as e:
    print(f"    ✗ Import failed: {e}")
    print("\n    Possible causes:")
    print("    • Missing dependencies")
    print("    • Syntax error in app.py")
    print("\n    Try running:")
    print("    pip3 install -r requirements.txt")
    print("    pip3 install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)
except Exception as e:
    print(f"    ✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Check 5: Verify youtube_config.json is valid JSON
print("\n[6] Checking youtube_config.json...")
if os.path.exists('youtube_config.json'):
    try:
        import json
        with open('youtube_config.json', 'r') as f:
            config = json.load(f)
        print("    ✓ Valid JSON")

        # Check structure
        if 'web' in config:
            print("    ✓ Has 'web' key")
            if 'client_id' in config['web']:
                print(f"    ✓ client_id: {config['web']['client_id'][:20]}...")
            else:
                print("    ✗ Missing 'client_id'")

            if 'redirect_uris' in config['web']:
                print(f"    ✓ redirect_uris: {config['web']['redirect_uris']}")
                if 'http://127.0.0.1:5050/oauth2callback' in config['web']['redirect_uris']:
                    print("    ✓ Correct redirect URI")
                else:
                    print("    ⚠️  Redirect URI might be incorrect")
            else:
                print("    ✗ Missing 'redirect_uris'")
        else:
            print("    ✗ Missing 'web' key in config")

    except json.JSONDecodeError as e:
        print(f"    ✗ Invalid JSON: {e}")
    except Exception as e:
        print(f"    ✗ Error reading config: {e}")
else:
    print("    ⚠️  youtube_config.json does not exist")
    print("    YouTube features will be disabled")

print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)

# Final summary
if missing_routes:
    print("\n❌ ISSUE: Code is out of date")
    print("   Solution: git pull origin claude/code-review-011CUP12EDoDPHQT1Khn8Les")
elif not os.path.exists('youtube_config.json'):
    print("\n⚠️  ISSUE: youtube_config.json missing")
    print("   Solution: Create youtube_config.json with OAuth credentials")
elif youtube_routes:
    print("\n✅ All checks passed!")
    print("   Routes should be working. Try:")
    print("   1. Restart Flask: python3 app.py")
    print("   2. Visit: http://127.0.0.1:5050")
else:
    print("\n❌ ISSUE: Routes not loading despite code being present")
    print("   This is unusual. Check for import errors above.")
