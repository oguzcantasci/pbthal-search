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
- Click the "Go to Forum Login" button to open the forum login page in a new tab
- After logging in to the forum, return to this app and try your search again
- The app will automatically detect when authentication is required and guide you to log in

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


