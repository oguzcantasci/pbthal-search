# PBTHAL Search Tool

A web-based search tool for finding vinyl rips on tonepoet.fans forum. Uses the forum's built-in search to find posts, then extracts and displays matching album download links in a clean, organized format.

## Features

- Search for artists or albums across forum posts
- Displays results as: "Album Name (Forum Post Title, Date)"
- Clickable links that take you directly to download pages
- Clean, simple web interface

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask server:
```bash
python app.py
```

3. Open your browser to `http://localhost:5001`

## Authentication

**Important:** The tonepoet.fans forum requires users to be logged in to search and access content. 

- When you perform a search, if you're not logged in, the app will display a login prompt
- Install a browser extension to export cookies (cookies.txt format):
  - Firefox: [cookies.txt](https://addons.mozilla.org/en-CA/firefox/addon/cookies-txt/)
  - Chrome: [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- Log in to tonepoet.fans, export your cookies, and upload the .txt file
- The app will validate your cookies and allow you to search

## Real-Debrid Integration

The tool includes Real-Debrid integration for unrestricted downloads:

1. Get your Real-Debrid API token from [real-debrid.com/apitoken](https://real-debrid.com/apitoken)
2. Enter your token in the Real-Debrid status section
3. Once connected, each search result will have an "Unrestrict via Real-Debrid" button
4. Click the button to unrestrict the link and start downloading

**Note:** This is a local application. Your API token is stored in the Flask session and never sent anywhere except to Real-Debrid's API.

## How It Works

1. User enters a search query (artist or album name)
2. Tool uses the forum's search API (`?s={query}`)
3. Scrapes search results to find matching posts
4. Extracts album download links from each post
5. Filters and displays matching links with post metadata

## Tech Stack

- Python Flask (backend)
- BeautifulSoup4 (web scraping)
- HTML/JavaScript (frontend)

## Deployment

This app can be deployed to Render's free tier. Here's how:

### Prerequisites
- A GitHub account
- Your code pushed to a GitHub repository

### Steps

1. **Sign up for Render**: Go to https://render.com and create a free account

2. **Create a Web Service**:
   - Click "New +" → "Web Service"
   - Connect your GitHub account
   - Select your `pbthal-search` repository

3. **Configure the Service**:
   - **Name**: `pbthal-search` (or any name you prefer)
   - **Region**: Choose closest to you
   - **Branch**: `main` (or your default branch)
   - **Root Directory**: Leave empty
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Plan**: Select "Free" tier

4. **Set Environment Variables**:
   - Scroll to "Environment Variables" section
   - Click "Add Environment Variable"
   - **Key**: `SECRET_KEY`
   - **Value**: Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`
   - Click "Save Changes"

5. **Deploy**:
   - Click "Create Web Service"
   - Wait for build to complete (2-5 minutes)
   - Your app will be live at `https://your-app-name.onrender.com`

### Notes
- Free tier instances sleep after 15 minutes of inactivity (first request may be slow)
- Free tier includes 750 hours/month (enough for 24/7 operation)
- Each user's credentials are stored in isolated server-side sessions


