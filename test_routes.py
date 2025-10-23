#!/usr/bin/env python3
"""
Quick test to check if YouTube routes are registered in your Flask app.
Run this in your lofimix folder: python3 test_routes.py
"""

import sys
import os

# Make sure we're in the right directory
if not os.path.exists('app.py'):
    print("❌ Error: app.py not found!")
    print("   Make sure you're running this from the lofimix directory")
    sys.exit(1)

try:
    import app

    print("✅ App imported successfully!")
    print(f"✅ YouTube enabled: {app.YOUTUBE_ENABLED}")

    # Check for YouTube-related routes
    youtube_routes = []
    oauth_routes = []

    for rule in app.app.url_map.iter_rules():
        rule_str = str(rule.rule)
        if 'youtube' in rule_str.lower():
            youtube_routes.append(rule_str)
        if 'oauth' in rule_str.lower():
            oauth_routes.append(rule_str)

    print("\n📍 YouTube Routes:")
    if youtube_routes:
        for route in youtube_routes:
            print(f"   ✓ {route}")
    else:
        print("   ❌ No YouTube routes found!")

    print("\n📍 OAuth Routes:")
    if oauth_routes:
        for route in oauth_routes:
            print(f"   ✓ {route}")
    else:
        print("   ❌ No OAuth routes found!")

    print(f"\n📊 Total routes registered: {len(list(app.app.url_map.iter_rules()))}")

    # Check for the critical route
    if '/oauth2callback' in [str(r.rule) for r in app.app.url_map.iter_rules()]:
        print("\n✅ SUCCESS: /oauth2callback route exists!")
        print("   Your code should work for YouTube authentication.")
    else:
        print("\n❌ PROBLEM: /oauth2callback route NOT found!")
        print("   You need to pull the latest code from git.")
        print("\n   Run this command:")
        print("   git pull origin claude/code-review-011CUP12EDoDPHQT1Khn8Les")

    # Check file size
    with open('app.py', 'r') as f:
        lines = len(f.readlines())

    print(f"\n📄 app.py has {lines} lines")
    if lines < 1000:
        print("   ⚠️  This seems too small! Expected ~1078 lines.")
        print("   You probably have old code. Pull latest from git.")
    else:
        print("   ✓ Line count looks good!")

except ImportError as e:
    print(f"❌ Error importing app: {e}")
    print("\nThis might mean:")
    print("  - Missing dependencies (run: pip install -r requirements.txt)")
    print("  - Wrong Python version")
    print("  - App code has syntax errors")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
