import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def scrape_url_to_json(url, max_pages=10, max_depth=10, progress_callback=None):
    """
    Utility function to scrape a URL and return JSON-compatible data with progress updates.
    
    Args:
        url (str): The URL to scrape (website or GitHub repository)
        max_pages (int): Maximum number of pages to scrape for websites (default: 10)
        max_depth (int): Maximum depth to scrape for websites (default: 10)
        progress_callback (callable): Function to update progress (takes current, total as args)
    
    Returns:
        dict: Scraped data as a JSON-compatible dictionary, or None if failed
    """
    
    # Website scraping helper
    def _scrape_website(start_url):
        def extract_links_and_content(url, current_depth):
            if current_depth > max_depth or len(visited) >= max_pages:
                return None
            
            try:
                response = requests.get(url, timeout=10)
                if response.status_code != 200:
                    return None
                    
                soup = BeautifulSoup(response.content, 'html.parser')
                
                content = {
                    "title": soup.title.string if soup.title else "No title",
                    "text": " ".join(p.get_text().strip() for p in soup.find_all('p')),
                    "url": url,
                    "links": []
                }
                
                for a_tag in soup.find_all('a', href=True):
                    full_url = urljoin(url, a_tag['href'])
                    if full_url not in visited:
                        content["links"].append(full_url)
                
                return content
                
            except Exception:
                return None

        visited = set()
        structure = {}
        to_visit = [(start_url, 0)]

        while to_visit and len(visited) < max_pages:
            current_url, depth = to_visit.pop(0)
            
            if current_url in visited:
                continue
                
            page_data = extract_links_and_content(current_url, depth)
            
            if page_data:
                visited.add(current_url)
                structure[current_url] = page_data
                
                # Update progress
                if progress_callback:
                    progress_callback(len(visited), max_pages)
                
                for link in page_data["links"]:
                    if link not in visited and len(visited) < max_pages:
                        to_visit.append((link, depth + 1))

        return structure

    # GitHub repo scraping helper
    def _scrape_repo(repo_url):
        skip_content_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ds_store"}
        skip_content_files = {".gitignore"}
        items_processed = 0
        total_items = 0
        
        def scrape_contents(api_url, total_count=None):
            nonlocal items_processed, total_items
            try:
                response = requests.get(api_url)
                if response.status_code != 200:
                    return None

                contents = response.json()
                if total_count is None:
                    total_items = len(contents)
                
                structure = {}

                for item in contents:
                    items_processed += 1
                    item_name = item["name"].lower()
                    
                    # Update progress
                    if progress_callback and total_items > 0:
                        progress_callback(items_processed, total_items)

                    if item["type"] == "file":
                        skip_content = (any(item_name.endswith(ext) for ext in skip_content_extensions) or 
                                      item_name in skip_content_files)
                        
                        if skip_content:
                            structure[item["name"]] = {"type": "file"}
                        else:
                            file_url = item["download_url"]
                            if file_url:
                                file_response = requests.get(file_url)
                                try:
                                    content_str = file_response.content.decode("utf-8")
                                    structure[item["name"]] = {
                                        "type": "file",
                                        "content": content_str
                                    }
                                except UnicodeDecodeError:
                                    structure[item["name"]] = {"type": "file"}
                            else:
                                structure[item["name"]] = {"type": "file"}
                                
                    elif item["type"] == "dir" and item_name != ".git":
                        dir_content = scrape_contents(item["url"], total_count or len(contents))
                        if dir_content:
                            structure[item["name"]] = {
                                "type": "dir",
                                "content": dir_content
                            }

                return structure if structure else None

            except requests.RequestException:
                return None

        if repo_url.startswith("https://github.com/"):
            repo_path = "/".join(repo_url.split("/")[3:5])
            api_url = f"https://api.github.com/repos/{repo_path}/contents"
        else:
            api_url = repo_url if repo_url.endswith("/contents") else f"{repo_url}/contents"
        
        return scrape_contents(api_url)

    # Main logic
    try:
        if "github.com" in url.lower():
            return _scrape_repo(url)
        else:
            return _scrape_website(url)
            
    except Exception as e:
        print(f"Error processing URL {url}: {str(e)}")
        return None