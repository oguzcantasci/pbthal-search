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

@app.route('/search', methods=['GET'])
def search():
    """Search endpoint for forum queries"""
    query = request.args.get('q', '')
    
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    # Scrape search results
    posts = scrape_search_results(query)
    
    # TODO: Scrape individual posts for album links
    return jsonify({'results': [], 'posts_found': len(posts)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

