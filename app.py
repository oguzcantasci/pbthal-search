from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, quote
import re

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

BASE_URL = 'https://tonepoet.fans'

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')

def scrape_search_results(query):
    """Scrape the forum search results page and extract post information
    Returns tuple: (posts, requires_auth) where requires_auth is True if login is needed"""
    search_url = f"{BASE_URL}/?s={quote(query)}"
    
    try:
        response = requests.get(search_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Check if authentication is required
        # Look for common login page indicators
        page_text = soup.get_text().lower()
        page_title = soup.find('title')
        title_text = page_title.get_text().lower() if page_title else ''
        
        # Check for login page indicators
        login_indicators = [
            'wp-login.php' in response.url.lower(),
            'log in' in title_text,
            'login' in title_text and 'required' in page_text,
            soup.find('form', {'id': 'loginform'}),
            soup.find('form', {'name': 'loginform'}),
            'you must be logged in' in page_text,
            'please log in' in page_text,
            'login required' in page_text
        ]
        
        requires_auth = any(login_indicators)
        
        if requires_auth:
            return [], True
        
        posts = []
        # Find all post entries in search results
        # WordPress typically uses article tags or divs with specific classes
        post_elements = soup.find_all(['article', 'div'], class_=lambda x: x and ('post' in x.lower() or 'entry' in x.lower()))
        
        # If no posts found with class, try finding h2 headings (post titles)
        if not post_elements:
            headings = soup.find_all('h2')
            for heading in headings:
                link = heading.find('a')
                if link:
                    post_url = urljoin(BASE_URL, link.get('href', ''))
                    post_title = heading.get_text(strip=True)
                    # Try to find date nearby
                    date_elem = heading.find_next(['time', 'span'], class_=lambda x: x and 'date' in x.lower() if x else False)
                    post_date = date_elem.get_text(strip=True) if date_elem else ''
                    posts.append({
                        'title': post_title,
                        'url': post_url,
                        'date': post_date
                    })
        else:
            for post_elem in post_elements:
                link = post_elem.find('a')
                if link:
                    post_url = urljoin(BASE_URL, link.get('href', ''))
                    post_title = link.get_text(strip=True) or post_elem.find(['h1', 'h2', 'h3'])
                    if isinstance(post_title, type(soup)):
                        post_title = post_title.get_text(strip=True)
                    date_elem = post_elem.find(['time', 'span'], class_=lambda x: x and 'date' in x.lower() if x else False)
                    post_date = date_elem.get_text(strip=True) if date_elem else ''
                    posts.append({
                        'title': post_title or 'Untitled',
                        'url': post_url,
                        'date': post_date
                    })
        
        return posts, False
    except Exception as e:
        print(f"Error scraping search results: {e}")
        return [], False

def scrape_post_album_links(post_url, query):
    """Scrape a single post page to extract album download links"""
    try:
        response = requests.get(post_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        
        album_links = []
        # Find all links in the post content
        # Look for links that might contain album names (Artist - Album format)
        content_area = soup.find(['article', 'div'], class_=lambda x: x and ('content' in x.lower() or 'entry' in x.lower() or 'post' in x.lower()) if x else False)
        
        if not content_area:
            # Fallback: search entire page
            content_area = soup
        
        # Find all links
        links = content_area.find_all('a', href=True)
        
        for link in links:
            link_text = link.get_text(strip=True)
            link_url = urljoin(BASE_URL, link.get('href', ''))
            
            # Check if link text contains the query (case-insensitive)
            # Also check for common album link patterns (Artist - Album)
            if query.lower() in link_text.lower() and link_text:
                # Additional check: should look like an album link (contains dash or common patterns)
                if ' - ' in link_text or len(link_text) > 5:
                    album_links.append({
                        'text': link_text,
                        'url': link_url
                    })
        
        return album_links
    except Exception as e:
        print(f"Error scraping post {post_url}: {e}")
        return []

def format_date(date_str):
    """Format date string to consistent format (e.g., 'September 2025')"""
    if not date_str:
        return ''
    
    # Try to extract month and year from various date formats
    # Look for patterns like "April 14, 2025" or "September 2025"
    date_str = date_str.strip()
    
    # Pattern for "Month Day, Year" or "Month Year"
    month_year_pattern = r'([A-Za-z]+)\s+(\d{4})'
    match = re.search(month_year_pattern, date_str)
    if match:
        month = match.group(1)
        year = match.group(2)
        return f"{month} {year}"
    
    return date_str

@app.route('/search', methods=['GET'])
def search():
    """Search endpoint for forum queries"""
    query = request.args.get('q', '')
    
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    try:
        # Scrape search results
        posts, requires_auth = scrape_search_results(query)
        
        if requires_auth:
            return jsonify({
                'results': [],
                'requiresAuth': True,
                'message': 'Please log in to the forum to search'
            })
        
        if not posts:
            return jsonify({'results': [], 'message': 'No posts found for this query'})
        
        # Scrape each post for album links
        results = []
        for post in posts:
            try:
                album_links = scrape_post_album_links(post['url'], query)
                post_date = format_date(post['date'])
                
                for link in album_links:
                    results.append({
                        'album': link['text'],
                        'url': link['url'],
                        'postTitle': post['title'],
                        'postDate': post_date
                    })
                
                # Add small delay to avoid overwhelming the server
                time.sleep(0.5)
            except Exception as e:
                print(f"Error processing post {post['url']}: {e}")
                continue
        
        return jsonify({'results': results})
    except Exception as e:
        print(f"Error in search endpoint: {e}")
        return jsonify({'error': 'An error occurred while searching', 'results': []}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)

