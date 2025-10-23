# Fix: "Access blocked - has not completed Google verification process"

This error occurs when your OAuth consent screen is in Production mode instead of Testing mode.

## Quick Fix (2 minutes)

### Step 1: Go to OAuth Consent Screen
1. Open: https://console.cloud.google.com/apis/credentials/consent
2. Make sure you've selected the correct project at the top

### Step 2: Change Publishing Status to TESTING

Look at the top of the page - you'll see a "Publishing status" section.

**If it says "In Production":**
1. Click "BACK TO TESTING" button (or similar)
2. Confirm the change

**If it says "Testing":**
- You're good! But continue to verify test users are added.

### Step 3: Verify Test Users

1. Scroll down to "Test users" section
2. Click "ADD USERS"
3. Add your Gmail address (the one you'll use to authenticate)
4. Click "SAVE"

### Step 4: Important Settings

Make sure these are set correctly:

**User Type:** Should be "External" (this is correct)

**Publishing status:** Should show "Testing" with this message:
- "Your application will be limited to 100 users while in testing mode"

### Step 5: Save Changes

1. Scroll to bottom
2. Click "SAVE AND CONTINUE" (if any changes were made)

### Step 6: Try Connecting Again

1. Go back to your app: http://127.0.0.1:5050
2. Scroll to YouTube section
3. Click "Connect YouTube Account"
4. You should now be able to authenticate!

## Why This Happens

- **Testing mode:** Allows you and up to 100 test users to authenticate without Google verification
- **Production mode:** Requires Google to verify your app (takes weeks and is for public apps)

Since this is your personal lofi mixer, you want **Testing mode**.

## Visual Guide

When you're on the OAuth consent screen page, you should see:

```
Publishing status: Testing
━━━━━━━━━━━━━━━━━━━━━━
Status: Testing
Your app is available to users you've added as test users.
```

NOT this:

```
Publishing status: In production
━━━━━━━━━━━━━━━━━━━━━━
Status: In production
Your app is available to all users.
```

## If "BACK TO TESTING" Button Doesn't Appear

1. Click "EDIT APP" button at the top
2. Go through the consent screen setup again
3. On the last page (Summary), look for publishing status options
4. Select "Testing"
5. Save changes

## Still Getting the Error?

Double-check these:

1. ✅ Publishing status = "Testing"
2. ✅ Your email is in test users list
3. ✅ You're using the SAME Google account that's a test user
4. ✅ The project is selected in Google Cloud Console

Then try clearing your browser cache or using an incognito window.

---

After making these changes, the authentication should work! 🎉
