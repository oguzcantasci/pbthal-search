from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import os
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, quote_plus
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for Flask sessions
CORS(app, supports_credentials=True)  # Enable credentials for cookie passthrough

BASE_URL = 'https://tonepoet.fans'

def get_authenticated_session():
    """Get or create a shared requests session with user's forum cookies"""
    # Use a shared session per user (stored in Flask session)
    # This allows WordPress to set additional session cookies that persist across requests
    session_key = 'requests_session'
    
    if session_key not in session:
        # Create new session
        user_session = requests.Session()
        user_session.trust_env = False  # ignore HTTP(S)_PROXY and similar env vars
        user_session.proxies = {"http": None, "https": None}
        user_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        })
        
        # Add stored cookies if available
        if 'forum_cookies' in session:
            user_session.cookies.update(session['forum_cookies'])
        
        # Store session object (Note: we can't pickle requests.Session, so we'll store cookies instead)
        # Actually, we can't store the session object directly in Flask session
        # Instead, we'll create a new session but restore cookies from Flask session
        # The key is to update Flask session cookies after each request
        return user_session
    else:
        # Reuse existing session by creating new one with stored cookies
        user_session = requests.Session()
        user_session.trust_env = False
        user_session.proxies = {"http": None, "https": None}
        user_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        })
        
        # Restore cookies from Flask session (including any new ones WordPress set)
        if 'forum_cookies' in session:
            user_session.cookies.update(session['forum_cookies'])
        
        return user_session

def update_session_cookies(user_session):
    """Update Flask session with cookies from requests session (including new ones WordPress might set)"""
    if user_session.cookies:
        # Update Flask session with all cookies from the requests session
        # This captures any new session cookies WordPress might set
        if 'forum_cookies' not in session:
            session['forum_cookies'] = {}
        
        # Update with all cookies from the session
        for cookie in user_session.cookies:
            session['forum_cookies'][cookie.name] = cookie.value

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')

def parse_netscape_cookies(cookie_file_content):
    """Parse Netscape cookie format (from browser extensions like cookies.txt)
    Format: domain	flag	path	secure	expiration	name	value
    """
    cookies_dict = {}
    for line in cookie_file_content.split('\n'):
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        
        # Parse tab-separated values
        parts = line.split('\t')
        if len(parts) >= 7:
            domain = parts[0]
            # flag = parts[1]  # Not needed
            # path = parts[2]  # Not needed
            # secure = parts[3]  # Not needed
            expiration = parts[4]
            name = parts[5]
            value = parts[6]
            
            # Check if cookie is expired (if expiration is not 0 and is in the past)
            if expiration != '0':
                try:
                    exp_time = int(expiration)
                    if exp_time < time.time():
                        print(f"  Skipping expired cookie: {name}")
                        continue
                except:
                    pass
            
            # Only include cookies for tonepoet.fans
            if 'tonepoet.fans' in domain:
                cookies_dict[name] = value
    
    return cookies_dict

@app.route('/set-cookies', methods=['POST'])
def set_cookies():
    """Store forum cookies from user's browser session
    Accepts either:
    - JSON with 'cookies' field (text format: "name1=value1; name2=value2")
    - JSON with 'cookieFile' field (Netscape format from browser extension)
    """
    try:
        # Check if it's a file upload (Netscape format)
        if 'cookieFile' in request.json:
            cookie_file_content = request.json.get('cookieFile', '')
            if not cookie_file_content:
                return jsonify({'error': 'No cookie file content provided'}), 400
            
            # Parse Netscape format
            cookies_dict = parse_netscape_cookies(cookie_file_content)
            
            if not cookies_dict:
                return jsonify({'error': 'No valid cookies found in file'}), 400
            
            print(f"\n=== COOKIE FILE PARSED ===")
            print(f"Parsed {len(cookies_dict)} cookies from Netscape format:")
            for name in cookies_dict.keys():
                print(f"  - {name}")
        
        # Otherwise, parse as text format
        elif 'cookies' in request.json:
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
        else:
            return jsonify({'error': 'No cookies or cookieFile provided'}), 400
        
        # Store in Flask session
        session['forum_cookies'] = cookies_dict
        print(f"Cookies stored in Flask session: {list(cookies_dict.keys())}")
        return jsonify({'success': True, 'message': f'Cookies saved successfully ({len(cookies_dict)} cookies)'})
    except Exception as e:
        print(f"Error saving cookies: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def scrape_search_results(query):
    """Scrape the forum search results page and extract post information
    Returns tuple: (posts, requires_auth) where requires_auth is True if login is needed"""
    search_url = f"{BASE_URL}/?s={quote_plus(query)}"
    
    # Use authenticated session with user's cookies
    user_session = get_authenticated_session()
    
    try:
        response = user_session.get(search_url, timeout=10, allow_redirects=True)
        response.raise_for_status()
        
        # Update Flask session with any new cookies WordPress might have set
        update_session_cookies(user_session)
        
        # Debug: Log response info
        print(f"Response status: {response.status_code}")
        print(f"Response URL: {response.url}")
        print(f"Response length: {len(response.text)} bytes")
        print(f"Cookies in request: {list(user_session.cookies.keys())}")
        
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
        # Look for divs with id="post-XXXX" pattern (actual search result posts)
        # Or h2.entry-title elements (post titles in search results)
        
        # Method 1: Find divs with post-XXXX id pattern
        post_elements = soup.find_all('div', id=lambda x: x and x.startswith('post-'))
        
        # Method 2: If that doesn't work, find h2.entry-title elements
        if not post_elements:
            entry_titles = soup.find_all('h2', class_='entry-title')
            for h2 in entry_titles:
                # Find the parent post div
                parent_post = h2.find_parent('div', id=lambda x: x and x.startswith('post-'))
                if parent_post:
                    post_elements.append(parent_post)
        
        # Check if all posts have restricted content
        restricted_posts_count = 0
        total_posts_found = 0
        
        for post_elem in post_elements:
            # Find the h2.entry-title link inside this post
            entry_title = post_elem.find('h2', class_='entry-title')
            if entry_title:
                link = entry_title.find('a')
                if link:
                    total_posts_found += 1
                    post_url = urljoin(BASE_URL, link.get('href', ''))
                    post_title = link.get_text(strip=True) or link.get('title', '')
                    
                    # Check if this post has restricted content
                    if post_elem.find('div', class_=lambda x: x and 'members-access-error' in str(x).lower() if x else False):
                        restricted_posts_count += 1
                    
                    # Try to find date nearby
                    date_elem = post_elem.find(['time', 'span'], class_=lambda x: x and 'date' in x.lower() if x else False)
                    post_date = date_elem.get_text(strip=True) if date_elem else ''
                    
                    posts.append({
                        'title': post_title,
                        'url': post_url,
                        'date': post_date
                    })
        
        # If we found posts but all of them are restricted, require authentication
        # Also check if any posts have restricted content - if most/all do, require auth
        if total_posts_found > 0:
            print(f"Found {total_posts_found} posts, {restricted_posts_count} are restricted")
            if restricted_posts_count == total_posts_found:
                print(f"All {total_posts_found} posts are restricted - authentication required")
                return [], True
            # If more than half the posts are restricted, likely need auth
            elif restricted_posts_count > 0 and (restricted_posts_count / total_posts_found) >= 0.5:
                print(f"{restricted_posts_count}/{total_posts_found} posts are restricted - authentication likely required")
                return [], True
        
        print(f"Returning {len(posts)} posts, auth not required")
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
        
        # Update Flask session with any new cookies WordPress might have set
        update_session_cookies(user_session)
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        album_links = []
        
        # Find ALL links on the page - no need to find specific divs
        all_links = soup.find_all('a', href=True)
        
        query_lower = query.lower()
        hexload_count = 0
        matching_count = 0
        
        for link in all_links:
            link_url = link.get('href', '')
            link_text = link.get_text(strip=True)
            
            # Filter: only hexload.com links
            if 'hexload.com' not in link_url:
                continue
            
            hexload_count += 1
            
            # Filter: link text must contain the query
            if not link_text or query_lower not in link_text.lower():
                continue
            
            matching_count += 1
            # Make sure URL is absolute
            full_url = urljoin(BASE_URL, link_url)
            
            album_links.append({
                'text': link_text,
                'url': full_url
            })
        
        print(f"  DEBUG: Total hexload.com links found: {hexload_count}")
        print(f"  DEBUG: Links matching query '{query}': {matching_count}")
        
        return album_links
    except Exception as e:
        print(f"Error scraping post {post_url}: {e}")
        import traceback
        traceback.print_exc()
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
    
    # Debug: Check if cookies are stored
    has_cookies = 'forum_cookies' in session
    print(f"\n=== SEARCH DEBUG for '{query}' ===")
    print(f"Has stored cookies: {has_cookies}")
    if has_cookies:
        print(f"Cookie names: {list(session['forum_cookies'].keys())}")
    
    try:
        # Scrape search results
        posts, requires_auth = scrape_search_results(query)
        
        print(f"Requires auth: {requires_auth}")
        print(f"Posts found: {len(posts)}")
        if posts:
            print("Posts detected:")
            for i, post in enumerate(posts, 1):
                print(f"  {i}. {post['title']} ({post['url']})")
        
        if requires_auth:
            return jsonify({
                'results': [],
                'requiresAuth': True,
                'message': 'Please log in to the forum to search',
                'debug': {
                    'hasCookies': has_cookies,
                    'cookieCount': len(session.get('forum_cookies', {}))
                }
            })
        
        if not posts:
            return jsonify({
                'results': [],
                'message': 'No posts found for this query',
                'debug': {
                    'hasCookies': has_cookies,
                    'cookieCount': len(session.get('forum_cookies', {})),
                    'requiresAuth': requires_auth
                }
            })
        
        # Scrape each post for album links
        results = []
        for post in posts:
            try:
                print(f"\nProcessing post: {post['title']}")
                album_links = scrape_post_album_links(post['url'], query)
                print(f"  Found {len(album_links)} album links in this post")
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
            print(f"Post URLs checked: {[post['url'] for post in posts[:3]]}")
            return jsonify({
                'results': [],
                'requiresAuth': True,
                'message': 'Please log in to the forum to search',
                'debug': {
                    'postsFound': len(posts),
                    'albumLinksFound': 0,
                    'hasCookies': has_cookies
                }
            })
        
        print(f"Successfully found {len(results)} album links")
        return jsonify({
            'results': results,
            'debug': {
                'postsFound': len(posts),
                'albumLinksFound': len(results),
                'hasCookies': has_cookies
            }
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Error in search endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'An error occurred while searching: {error_msg}', 'results': []}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)

