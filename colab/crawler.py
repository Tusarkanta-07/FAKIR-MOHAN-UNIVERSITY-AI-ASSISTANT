# =============================================================================
# 🕷️ CHATBASE CLONE — WEBSITE CRAWLER FOR GOOGLE COLAB
# =============================================================================
# Copy-paste this entire file into a Google Colab notebook (one cell per section)
# Or upload as .py and run cells with %run
#
# SECTIONS:
#   1. Install Dependencies
#   2. Configuration
#   3. Crawler Engine
#   4. Run Crawler
#   5. Chunk Text for RAG
#   6. Upload to Hugging Face Backend
# =============================================================================

# %%
# =============================================================================
# CELL 1: Install Dependencies
# =============================================================================
# !pip install requests beautifulsoup4 lxml tqdm

# %%
# =============================================================================
# CELL 2: Configuration
# =============================================================================

CONFIG = {
    "start_url": "https://fmuniversity.nic.in",  # 🔧 CHANGE THIS — website to crawl
    "max_pages": 1000,                         # Max pages to crawl
    "max_depth": 10,                           # Max link depth from start URL
    "max_time": 60 * 60,                       # ⏱️ Max crawl time in seconds (30 minutes)
    "page_timeout": 120,                       # ⏱️ Per-page request timeout (seconds, 2 mins)
    "retry_timeout": 120,                      # ⏱️ Retry timeout for failed pages
    "max_retries": 1,                          # Max retries per page
    "crawl_delay": 0.5,                        # Seconds between requests
    "chatbot_name": "fmu-chatbot",             # Name for your chatbot
    "output_dir": "/content/crawl_output",     # Output directory (Colab default)
    "chunk_size": 500,                         # Words per chunk
    "chunk_overlap": 50,                       # Overlap words between chunks
    "verify_ssl": False,                       # ⚠️ Set False for sites with expired SSL certs
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "backend_url": "https://YOUR-SPACE.hf.space",  # 🔧 CHANGE — your HF Space URL
    "skip_urls": [                             # 🚫 Exact URLs to skip
        "https://fmuniversity.nic.in/IDP_information.html",
        "https://fmuniversity.nic.in/IQAC_information.html",
        "https://fmuniversity.nic.in/NAAC_information.html",
        "https://fmuniversity.nic.in/NIRF_information.html",
        "https://fmuniversity.nic.in/mous.html",
        "https://fmuniversity.nic.in/archives.html",
        "https://fmuniversity.nic.in/getdata"
    ],
}

# %%
# =============================================================================
# CELL 3: Crawler Engine
# =============================================================================

import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
import time
import re
from collections import deque
from tqdm import tqdm

# Suppress SSL warnings for sites with expired/invalid certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class WebsiteCrawler:
    """Crawls a website and extracts text, PDF links, and image URLs."""

    def __init__(self, config):
        self.config = config
        self.visited = set()
        self.results = []
        self.verify_ssl = config.get("verify_ssl", True)
        self.session = requests.Session()
        self.session.verify = self.verify_ssl  # Disable SSL verification if needed
        self.session.headers.update({
            "User-Agent": config["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.base_domain = urlparse(config["start_url"]).netloc
        os.makedirs(config["output_dir"], exist_ok=True)
        if not self.verify_ssl:
            print("⚠️  SSL verification DISABLED — use only for trusted sites with expired certs")

    def is_valid_url(self, url):
        """Check if URL belongs to the same domain and is crawlable."""
        parsed = urlparse(url)
        if parsed.netloc:
            base = self.base_domain.replace('www.', '')
            target = parsed.netloc.replace('www.', '')
            if base != target:
                return False
            
        # Skip URLs if they contain any of the skip strings
        for skip in self.config.get('skip_urls', []):
            if skip in url:
                return False

        # Skip non-page resources (including docs and images to speed up scraping)
        skip_extensions = {'.zip', '.exe', '.dmg', '.mp4', '.mp3', '.avi', '.mov',
                          '.tar', '.gz', '.rar', '.7z', '.css', '.js', '.woff',
                          '.woff2', '.ttf', '.eot', '.svg', '.ico',
                          '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.csv'}
        path_lower = parsed.path.lower()
        for ext in skip_extensions:
            if path_lower.endswith(ext):
                return False
        # Skip anchors and mailto
        if url.startswith(('mailto:', 'tel:', 'javascript:')):
            return False
        return True

    def extract_text(self, soup):
        """Extract visible text from a BeautifulSoup object."""
        # Remove script, style, nav, footer, header elements
        for element in soup.find_all(['script', 'style', 'nav', 'footer', 'noscript', 'iframe']):
            element.decompose()

        # Get text
        text = soup.get_text(separator='\n', strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = '\n'.join(lines)

        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text

    def extract_links(self, soup, current_url):
        """Extract all links from the page."""
        links = set()
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(current_url, href)
            # Remove fragment
            full_url = full_url.split('#')[0]
            if full_url and self.is_valid_url(full_url):
                links.add(full_url)
        return links

    def crawl_page(self, url):
        """Crawl a single page with timeout and retry."""
        timeout = self.config.get('page_timeout', 8)
        retries = self.config.get('max_retries', 1)
        retry_timeout = self.config.get('retry_timeout', 5)

        for attempt in range(1 + retries):
            try:
                t = retry_timeout if attempt > 0 else timeout
                response = self.session.get(url, timeout=t, allow_redirects=True)
                response.raise_for_status()

                # Only parse HTML pages
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' not in content_type:
                    return None

                soup = BeautifulSoup(response.text, 'lxml')

                # Extract title
                title_tag = soup.find('title')
                title = title_tag.get_text(strip=True) if title_tag else url

                # Extract meta description
                meta_desc = ''
                meta_tag = soup.find('meta', attrs={'name': 'description'})
                if meta_tag and meta_tag.get('content'):
                    meta_desc = meta_tag['content']

                # Extract links first before the soup tree is mutated by extract_text!
                links = self.extract_links(soup, url)
                text = self.extract_text(soup)

                return {
                    'url': url,
                    'title': title,
                    'meta_description': meta_desc,
                    'text': text,
                    'links': links,
                }

            except requests.Timeout:
                if attempt < retries:
                    print(f"  ⏱️  Timeout on {url}, retrying ({attempt+1}/{retries})...")
                else:
                    print(f"  ⏱️  Skipping {url} — timed out after {retries+1} attempts")
                    self.failed_count += 1
                    return None

            except requests.RequestException as e:
                print(f"  ⚠️  Failed to crawl {url}: {e}")
                self.failed_count += 1
                return None

    def crawl(self):
        """BFS crawl with total time limit."""
        max_time = self.config.get('max_time', 20 * 60)  # default 20 min
        self.failed_count = 0

        print(f"🕷️  Starting crawl of: {self.config['start_url']}")
        print(f"   Max pages: {self.config['max_pages']} | Max depth: {self.config['max_depth']}")
        print(f"   ⏱️  Time limit: {max_time // 60} minutes")
        print(f"   Page timeout: {self.config.get('page_timeout', 8)}s | Delay: {self.config['crawl_delay']}s")
        print("=" * 60)

        start_time = time.time()

        # BFS queue: (url, depth)
        queue = deque([(self.config['start_url'], 0)])
        self.visited.add(self.config['start_url'])

        pbar = tqdm(total=self.config['max_pages'], desc="Crawling pages")

        while queue and len(self.results) < self.config['max_pages']:
            # ⏱️ Check time limit
            elapsed = time.time() - start_time
            remaining = max_time - elapsed
            if remaining <= 0:
                print(f"\n⏱️  Time limit reached ({max_time // 60} min). Stopping crawl.")
                break

            url, depth = queue.popleft()
            page_num = len(self.results) + 1
            short_url = url if len(url) < 80 else url[:77] + '...'
            print(f"\n📄 [{page_num}/{self.config['max_pages']}] Depth:{depth} → {short_url}")

            # Crawl the page
            page_data = self.crawl_page(url)

            if page_data:
                title = page_data['title'][:60] if page_data['title'] else 'No title'
                text_len = len(page_data['text'])
                links_found = len(page_data['links'])
                print(f"   ✅ \"{title}\" — {text_len} chars, {links_found} links")

                # Store results
                self.results.append({
                    'url': page_data['url'],
                    'title': page_data['title'],
                    'meta_description': page_data['meta_description'],
                    'text': page_data['text'],
                })

                pbar.update(1)
                mins_left = remaining / 60
                pbar.set_postfix({"depth": depth, "queued": len(queue), "⏱️": f"{mins_left:.1f}m left"})

                # Add new links to queue if within depth
                if depth < self.config['max_depth']:
                    for link in page_data['links']:
                        if link not in self.visited:
                            self.visited.add(link)
                            queue.append((link, depth + 1))

            # Polite delay
            time.sleep(self.config['crawl_delay'])

        pbar.close()

        elapsed = time.time() - start_time
        print(f"\n✅ Crawl complete in {elapsed/60:.1f} minutes!")
        print(f"   📄 Pages crawled: {len(self.results)}")
        print(f"   ⏭️  Pages skipped/failed: {self.failed_count}")
        print(f"   🔗 URLs visited: {len(self.visited)}")

    def save(self):
        """Save crawl results to JSON files."""
        # Main dataset
        dataset = {
            "chatbot_id": self.config['chatbot_name'],
            "source_url": self.config['start_url'],
            "crawled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_pages": len(self.results),
            "pages": self.results,
        }

        dataset_path = os.path.join(self.config['output_dir'], 'dataset.json')
        with open(dataset_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        print(f"💾 Dataset saved to: {dataset_path}")

        return dataset

# %%
# =============================================================================
# CELL 4: Run the Crawler
# =============================================================================

crawler = WebsiteCrawler(CONFIG)
crawler.crawl()
dataset = crawler.save()

# %%
# =============================================================================
# CELL 5: Chunk Text for RAG (Make AI-Ready)
# =============================================================================

def chunk_text(text, chunk_size=500, overlap=50):
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = ' '.join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap  # Overlap

    return chunks


def create_chunks(dataset, config):
    """Create AI-ready chunks from the crawled dataset."""
    print("🔄 Creating AI-ready chunks...")

    all_chunks = []
    chunk_id = 0

    for page in dataset['pages']:
        text = page['text']
        if not text or len(text.strip()) < 50:
            continue

        # Prepend title and meta for context
        header = ""
        if page['title']:
            header += f"Page: {page['title']}\n"
        if page['meta_description']:
            header += f"Description: {page['meta_description']}\n"
        header += f"URL: {page['url']}\n\n"

        page_chunks = chunk_text(text, config['chunk_size'], config['chunk_overlap'])

        for i, chunk in enumerate(page_chunks):
            all_chunks.append({
                "chunk_id": chunk_id,
                "source_url": page['url'],
                "page_title": page['title'],
                "chunk_index": i,
                "total_chunks": len(page_chunks),
                "content": header + chunk,
            })
            chunk_id += 1

    # Save chunks
    chunks_data = {
        "chatbot_id": config['chatbot_name'],
        "source_url": config['start_url'],
        "total_chunks": len(all_chunks),
        "chunk_config": {
            "chunk_size": config['chunk_size'],
            "overlap": config['chunk_overlap'],
        },
        "chunks": all_chunks,
    }

    chunks_path = os.path.join(config['output_dir'], 'chunks.json')
    with open(chunks_path, 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Created {len(all_chunks)} chunks from {len(dataset['pages'])} pages")
    print(f"💾 Chunks saved to: {chunks_path}")

    return chunks_data


chunks_data = create_chunks(dataset, CONFIG)

# %%
# =============================================================================
# CELL 6: Upload Chunks to Hugging Face Backend
# =============================================================================

def upload_to_backend(chunks_data, config):
    """Upload chunks to the Hugging Face Spaces backend."""
    backend_url = config['backend_url'].rstrip('/')
    endpoint = f"{backend_url}/api/chatbot"

    print(f"🚀 Uploading to backend: {endpoint}")
    print(f"   Chatbot: {chunks_data['chatbot_id']}")
    print(f"   Chunks: {chunks_data['total_chunks']}")

    try:
        response = requests.post(
            endpoint,
            json=chunks_data,
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        print(f"✅ Upload successful!")
        print(f"   Chatbot ID: {result.get('chatbot_id', 'N/A')}")
        print(f"   Status: {result.get('status', 'N/A')}")
        return result

    except requests.RequestException as e:
        print(f"❌ Upload failed: {e}")
        print(f"   Make sure your backend is running at: {backend_url}")
        print(f"   You can also manually upload chunks.json via the API")
        return None


# 🔧 Uncomment the line below after setting your backend_url in CONFIG
# upload_result = upload_to_backend(chunks_data, CONFIG)

print("\n📋 To manually upload, use this curl command:")
print(f'curl -X POST {CONFIG["backend_url"]}/api/chatbot \\')
print(f'  -H "Content-Type: application/json" \\')
print(f'  -d @{CONFIG["output_dir"]}/chunks.json')
