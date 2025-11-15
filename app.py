from flask import Flask, request, jsonify, send_from_directory
import os
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, quote

app = Flask(__name__)

BASE_URL = 'https://tonepoet.fans'

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')

def scrape_search_results(query):
    """Scrape the forum search results page and extract post information"""
    search_url = f"{BASE_URL}/?s={quote(query)}"
    
    try:
        response = requests.get(search_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        
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
        
        return posts
    except Exception as e:
        print(f"Error scraping search results: {e}")
        return []

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
    # This is a simple implementation - can be enhanced
    return date_str.strip()

@app.route('/search', methods=['GET'])
def search():
    """Search endpoint for forum queries"""
    query = request.args.get('q', '')
    
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    # Scrape search results
    posts = scrape_search_results(query)
    
    # Scrape each post for album links
    results = []
    for post in posts:
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
    
    return jsonify({'results': results})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

