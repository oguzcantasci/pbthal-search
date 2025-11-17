from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import os
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, quote
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for Flask sessions
CORS(app, supports_credentials=True)  # Enable credentials for cookie passthrough

BASE_URL = 'https://tonepoet.fans'

def get_authenticated_session():
    """Get a requests session with user's forum cookies if available"""
    user_session = requests.Session()
    user_session.trust_env = False  # ignore HTTP(S)_PROXY and similar env vars
    user_session.proxies = {"http": None, "https": None}
    user_session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    })
    
    # Add stored cookies if available
    if 'forum_cookies' in session:
        user_session.cookies.update(session['forum_cookies'])
    
    return user_session

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')

@app.route('/set-cookies', methods=['POST'])
def set_cookies():
    """Store forum cookies from user's browser session"""
    try:
        cookies_str = request.json.get('cookies', '')
        if not cookies_str:
            return jsonify({'error': 'No cookies provided'}), 400
        
        # Parse cookie string (format: "name1=value1; name2=value2")
        cookies_dict = {}
        for cookie in cookies_str.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                cookies_dict[name.strip()] = value.strip()
        
        # Store in Flask session
        session['forum_cookies'] = cookies_dict
        return jsonify({'success': True, 'message': 'Cookies saved successfully'})
    except Exception as e:
        print(f"Error saving cookies: {e}")
        return jsonify({'error': str(e)}), 500

def scrape_search_results(query):
    """Scrape the forum search results page and extract post information
    Returns tuple: (posts, requires_auth) where requires_auth is True if login is needed"""
    search_url = f"{BASE_URL}/?s={quote(query)}"
    
    # Use authenticated session with user's cookies
    user_session = get_authenticated_session()
    
    try:
        response = user_session.get(search_url, timeout=10, allow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        
        # First-post authentication check: if the first post body shows restricted message, require login
        try:
            first_post_elem = None
            tentative_posts = soup.find_all(['article', 'div'], class_=lambda x: x and ('post' in x.lower() or 'entry' in x.lower()))
            if tentative_posts:
                first_post_elem = tentative_posts[0]
            else:
                first_heading = soup.find('h2')
                if first_heading:
                    first_post_elem = first_heading.find_parent(['article', 'div']) or first_heading
            if first_post_elem is not None:
                first_post_html = str(first_post_elem).lower()
                if ('members-access-error' in first_post_html) or ('sorry, but you do not have permission to view this content' in first_post_html):
                    print("Authentication required: first post is restricted")
                    return [], True
        except Exception as _:
            # Non-fatal: continue with other detection methods
            pass
        
        # Check if authentication is required
        # Look for common login page indicators
        page_text = soup.get_text().lower()
        page_html = str(soup).lower()
        page_title = soup.find('title')
        title_text = page_title.get_text().lower() if page_title else ''
        
        # Check for the exact permission error text or partial matches
        response_text = response.text
        response_lower = response_text.lower()
        
        # Check for various forms of the permission error
        permission_indicators = [
            'sorry, but you do not have permission to view this content',
            'do not have permission to view this content',
            'please register in order to view this',
            'members-access-error'
        ]
        
        for indicator in permission_indicators:
            if indicator in response_lower:
                print(f"Authentication required: found '{indicator}'")
                return [], True
        
        # Try multiple ways to find it in parsed soup
        members_error_div = (soup.find('div', class_='members-access-error') or 
                            soup.find('div', class_=lambda x: x and 'members-access-error' in str(x) if x else False))
        if members_error_div:
            print(f"Authentication required: found members-access-error div")
            return [], True
        
        # Check for login page indicators
        login_indicators = [
            'wp-login.php' in response.url.lower(),
            'log in' in title_text,
            'login' in title_text and 'required' in page_text,
            soup.find('form', {'id': 'loginform'}),
            soup.find('form', {'name': 'loginform'}),
            'you must be logged in' in page_text,
            'please log in' in page_text,
            'login required' in page_text,
            'you do not have permission to view this content' in page_text,
            'members-access-error' in page_html,
            'please register in order to view this' in page_text,
            'do not have permission' in page_text
        ]
        
        requires_auth = any(login_indicators)
        
        if requires_auth:
            print(f"Authentication required detected for query: {query}")
            return [], True
        
        posts = []
        # Find all post entries in search results
        # WordPress typically uses article tags or divs with specific classes
        post_elements = soup.find_all(['article', 'div'], class_=lambda x: x and ('post' in x.lower() or 'entry' in x.lower()))
        
        # Check if all posts have restricted content
        restricted_posts_count = 0
        total_posts_found = 0
        
        # If no posts found with class, try finding h2 headings (post titles)
        if not post_elements:
            headings = soup.find_all('h2')
            for heading in headings:
                link = heading.find('a')
                if link:
                    total_posts_found += 1
                    post_url = urljoin(BASE_URL, link.get('href', ''))
                    post_title = heading.get_text(strip=True)
                    # Check if this post has restricted content
                    post_content = heading.find_next(['div', 'article'], class_=lambda x: x and ('content' in x.lower() or 'entry' in x.lower() or 'post' in x.lower()) if x else False)
                    if post_content:
                        if post_content.find('div', class_=lambda x: x and 'members-access-error' in str(x).lower() if x else False):
                            restricted_posts_count += 1
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
                    total_posts_found += 1
                    post_url = urljoin(BASE_URL, link.get('href', ''))
                    post_title = link.get_text(strip=True) or post_elem.find(['h1', 'h2', 'h3'])
                    if isinstance(post_title, type(soup)):
                        post_title = post_title.get_text(strip=True)
                    # Check if this post has restricted content
                    if post_elem.find('div', class_=lambda x: x and 'members-access-error' in str(x).lower() if x else False):
                        restricted_posts_count += 1
                    date_elem = post_elem.find(['time', 'span'], class_=lambda x: x and 'date' in x.lower() if x else False)
                    post_date = date_elem.get_text(strip=True) if date_elem else ''
                    posts.append({
                        'title': post_title or 'Untitled',
                        'url': post_url,
                        'date': post_date
                    })
        
        # If we found posts but all of them are restricted, require authentication
        # Also check if any posts have restricted content - if most/all do, require auth
        if total_posts_found > 0:
            if restricted_posts_count == total_posts_found:
                print(f"All {total_posts_found} posts are restricted - authentication required")
                return [], True
            # If more than half the posts are restricted, likely need auth
            elif restricted_posts_count > 0 and (restricted_posts_count / total_posts_found) >= 0.5:
                print(f"{restricted_posts_count}/{total_posts_found} posts are restricted - authentication likely required")
                return [], True
        
        return posts, False
    except Exception as e:
        print(f"Error scraping search results: {e}")
        return [], False

def scrape_post_album_links(post_url, query):
    """Scrape a single post page to extract album download links"""
    # Use authenticated session with user's cookies
    user_session = get_authenticated_session()
    
    try:
        response = user_session.get(post_url, timeout=10, allow_redirects=True)
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
        
        # If we found posts but no album links, likely need authentication
        if len(posts) > 0 and len(results) == 0:
            print(f"Found {len(posts)} posts but no album links - authentication likely required")
            return jsonify({
                'results': [],
                'requiresAuth': True,
                'message': 'Please log in to the forum to search'
            })
        
        return jsonify({'results': results})
    except Exception as e:
        error_msg = str(e)
        print(f"Error in search endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'An error occurred while searching: {error_msg}', 'results': []}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)

