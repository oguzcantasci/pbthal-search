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


