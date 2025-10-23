# YouTube Live Streaming Setup Guide

Follow these steps to enable YouTube Live Streaming in Lofi Mixer Studio.

## Step 1: Install Python Dependencies

First, install the required Python libraries:

```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## Step 2: Create Google Cloud Project

### 2.1 Go to Google Cloud Console
1. Open: https://console.cloud.google.com/
2. Sign in with your Google account (the one connected to your YouTube channel)

### 2.2 Create a New Project
1. Click the project dropdown at the top (says "Select a project")
2. Click "NEW PROJECT"
3. Enter project name: `Lofi Mixer Studio` (or any name you prefer)
4. Click "CREATE"
5. Wait for the project to be created (takes a few seconds)
6. Select your new project from the dropdown

## Step 3: Enable YouTube Data API v3

### 3.1 Navigate to APIs
1. In the left sidebar, click "APIs & Services" → "Library"
   (Or go to: https://console.cloud.google.com/apis/library)

### 3.2 Enable the API
1. In the search box, type: `YouTube Data API v3`
2. Click on "YouTube Data API v3" from the results
3. Click the blue "ENABLE" button
4. Wait for it to enable (takes a few seconds)

## Step 4: Configure OAuth Consent Screen

### 4.1 Navigate to OAuth Consent
1. Click "APIs & Services" → "OAuth consent screen" in left sidebar
   (Or go to: https://console.cloud.google.com/apis/credentials/consent)

### 4.2 Configure Consent Screen
1. **User Type**: Select "External"
2. Click "CREATE"

### 4.3 Fill Out App Information
1. **App name**: `Lofi Mixer Studio`
2. **User support email**: Select your email from dropdown
3. **App logo**: (Optional - skip for now)
4. **Application home page**: (Optional - leave blank)
5. **Authorized domains**: (Leave blank for local development)
6. **Developer contact information**: Enter your email
7. Click "SAVE AND CONTINUE"

### 4.4 Scopes
1. Click "ADD OR REMOVE SCOPES"
2. In the filter box, type: `youtube.force-ssl`
3. Check the box for: `https://www.googleapis.com/auth/youtube.force-ssl`
   - This scope allows: "See, edit, and permanently delete your YouTube videos, ratings, comments and captions"
4. Click "UPDATE"
5. Click "SAVE AND CONTINUE"

### 4.5 Test Users
1. Click "ADD USERS"
2. Enter your Gmail address (the one you'll use to stream)
3. Click "ADD"
4. Click "SAVE AND CONTINUE"

### 4.6 Summary
1. Review the information
2. Click "BACK TO DASHBOARD"

## Step 5: Create OAuth 2.0 Credentials

### 5.1 Navigate to Credentials
1. Click "APIs & Services" → "Credentials" in left sidebar
   (Or go to: https://console.cloud.google.com/apis/credentials)

### 5.2 Create OAuth Client ID
1. Click "+ CREATE CREDENTIALS" at the top
2. Select "OAuth client ID"

### 5.3 Configure Client ID
1. **Application type**: Select "Web application"
2. **Name**: `Lofi Mixer Local`
3. **Authorized JavaScript origins**: (Leave blank)
4. **Authorized redirect URIs**: Click "ADD URI"
   - Enter EXACTLY: `http://127.0.0.1:5050/oauth2callback`
   - ⚠️ IMPORTANT: Use `127.0.0.1` NOT `localhost`
5. Click "CREATE"

### 5.4 Download Credentials
1. A popup will show your Client ID and Client Secret
2. Click "DOWNLOAD JSON"
3. Save the file (it will be named something like `client_secret_xxxxx.json`)

## Step 6: Configure Lofi Mixer Studio

### 6.1 Open the Downloaded JSON File
1. Open the JSON file you just downloaded in a text editor
2. It should look something like this:

```json
{
  "web": {
    "client_id": "123456789-abcdefg.apps.googleusercontent.com",
    "project_id": "lofi-mixer-xxxxx",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "GOCSPX-xxxxxxxxxxxxxxxx",
    "redirect_uris": ["http://127.0.0.1:5050/oauth2callback"]
  }
}
```

### 6.2 Create youtube_config.json
1. In your `lofimix` project folder, you should see `youtube_config.example.json`
2. Copy the ENTIRE contents from the downloaded JSON file
3. Create a NEW file named `youtube_config.json` (remove the .example)
4. Paste the contents into `youtube_config.json`
5. Save the file

### 6.3 Verify File Location
Make sure your project structure looks like this:
```
lofimix/
├── app.py
├── requirements.txt
├── youtube_config.json  ← NEW FILE (not tracked by git)
├── youtube_config.example.json
├── static/
│   └── app.js
└── ...
```

## Step 7: Restart the Server

1. If the Flask server is running, stop it (Ctrl+C)
2. Start it again:
   ```bash
   python3 app.py
   ```
3. You should see no errors about YouTube

## Step 8: Test the Setup

### 8.1 Open the Application
1. Go to: http://127.0.0.1:5050
2. Scroll down to the "🔴 YouTube Live Streaming" section

### 8.2 Connect Your YouTube Account
1. You should now see a blue box saying "Connect Your YouTube Account"
2. Click the "Connect YouTube Account" button
3. You'll be redirected to Google's login page

### 8.3 Authenticate
1. Sign in with your Google account (if not already signed in)
2. You may see a warning "Google hasn't verified this app"
   - Click "Advanced"
   - Click "Go to Lofi Mixer Studio (unsafe)"
   - This is safe because you created the app yourself
3. Review the permissions
4. Click "Allow"
5. You'll be redirected back to the app

### 8.4 Verify Success
1. You should see "Successfully connected to YouTube!" alert
2. The YouTube section should now show:
   - ✅ Green "YouTube Connected" badge
   - Upload Video section
   - Video Library table

## Step 9: Test Streaming

### 9.1 Upload a Test Video (Optional)
1. In the YouTube section, click the file upload
2. Select any MP4 video file
3. Click "Upload Video"
4. Wait for upload to complete

### 9.2 Stream a Video
1. You should see your video in the library
2. Click the red "Go Live" button
3. Enter a stream title
4. Enter a description
5. Choose Public or Unlisted (click Cancel for Unlisted)
6. Stream will start!

## Troubleshooting

### "YouTube integration not configured"
- Make sure `youtube_config.json` exists in the project root
- Verify the JSON is valid (no syntax errors)
- Restart the Flask server

### "Redirect URI mismatch" error
- Go back to Google Cloud Console → Credentials
- Edit your OAuth client
- Make sure redirect URI is EXACTLY: `http://127.0.0.1:5050/oauth2callback`
- Use `127.0.0.1` not `localhost`

### "Google hasn't verified this app" warning
- This is normal for personal projects
- Click "Advanced" → "Go to Lofi Mixer Studio (unsafe)"
- It's safe because you created the app

### "Access blocked: This app's request is invalid"
- Check that YouTube Data API v3 is enabled
- Verify the scope `youtube.force-ssl` is added in OAuth consent screen
- Make sure you're using the correct Google account

### "Insufficient permissions" error
- Go to OAuth consent screen
- Make sure your email is added as a test user
- Re-authenticate by clicking "Connect YouTube Account" again

## Security Notes

⚠️ **IMPORTANT**:
- `youtube_config.json` contains sensitive credentials
- It's already in `.gitignore` and won't be committed to git
- Never share this file publicly
- If you accidentally expose it, regenerate credentials in Google Cloud Console

## Need More Help?

If you encounter any issues:
1. Check the terminal where Flask is running for error messages
2. Look in the browser console (F12) for JavaScript errors
3. Verify all steps were followed exactly
4. Make sure you're using the correct Google account that has a YouTube channel

## Quick Reference: Important URLs

- Google Cloud Console: https://console.cloud.google.com/
- API Library: https://console.cloud.google.com/apis/library
- Credentials: https://console.cloud.google.com/apis/credentials
- OAuth Consent: https://console.cloud.google.com/apis/credentials/consent

---

After completing these steps, you'll be able to stream your lofi videos directly to YouTube Live! 🎉
