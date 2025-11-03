"""
DuckDuckGo Scraper for Business Information
Searches DuckDuckGo and extracts business info from result websites
"""

import asyncio
import logging
import re
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DuckDuckGoScraper:
    """Scraper for DuckDuckGo search results"""

    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self.browser = None
        self.context = None

    async def scrape(self, keyword: str, location: str = "", max_results: int = 10) -> List[Dict]:
        """
        Search DuckDuckGo and extract business info from result websites

        Args:
            keyword: Search keyword (e.g., "cửa hàng hải sản")
            location: Location to include in search (e.g., "hà nội")
            max_results: Maximum number of websites to scrape

        Returns:
            List of business data dictionaries
        """
        logger.info(f"=== DUCKDUCKGO SCRAPER ===")
        logger.info(f"Search: {keyword} {location}")

        async with async_playwright() as p:
            # Launch with stealth options
            self.browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )

            # Add stealth scripts
            await self.context.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                // Add chrome object
                window.chrome = { runtime: {} };
            """)

            try:
                # Step 1: Get URLs from DuckDuckGo
                urls = await self._search_duckduckgo(keyword, location, max_results)
                logger.info(f"✓ Found {len(urls)} URLs from DuckDuckGo")

                if not urls:
                    logger.warning("No URLs found")
                    return []

                # Step 2: Scrape each website for business info
                businesses = await self._scrape_websites(urls, max_results)
                logger.info(f"✓ Extracted {len(businesses)} businesses")

                return businesses

            except Exception as e:
                logger.error(f"Scrape error: {str(e)}")
                return []
            finally:
                await self.browser.close()

    async def _search_duckduckgo(self, keyword: str, location: str, max_results: int) -> List[Dict]:
        """
        Search DuckDuckGo and extract result URLs

        Returns:
            List of dicts with 'url', 'title', 'snippet'
        """
        page = await self.context.new_page()

        try:
            # Build search query
            query = f"{keyword} {location}".strip()
            search_url = f"https://duckduckgo.com/?q={query}&ia=web"

            logger.info(f"URL: {search_url}")

            # Go to page and wait for load
            try:
                await page.goto(search_url, wait_until='domcontentloaded', timeout=self.timeout)
                # Wait for page to be stable after any redirects
                await page.wait_for_load_state('networkidle', timeout=15000)
            except Exception as nav_error:
                logger.warning(f"Navigation warning: {nav_error}")
                # Continue anyway, page might be loaded
                await asyncio.sleep(5)

            # CRITICAL: Wait for search results to render
            # DuckDuckGo is SPA - need to wait for React to render results
            logger.info("Waiting for results to render...")

            try:
                # Wait for results container
                await page.wait_for_selector('article[data-testid="result"]', timeout=15000)
                logger.info("✓ Results container found")
            except Exception as e:
                logger.warning(f"Timeout waiting for results: {e}")
                # Still try to continue

            # Extra wait for all results to render
            await asyncio.sleep(3)

            # Take screenshot for debugging
            try:
                await page.screenshot(path='duckduckgo_debug.png')
                logger.info("Screenshot saved: duckduckgo_debug.png")
            except:
                pass

            # Extra stabilization wait after screenshot
            await asyncio.sleep(2)

            # Extract search results using EXACT selectors from inspect
            results = []

            # CRITICAL FIX: Get HTML content first, THEN query
            # This avoids timing issues with React rendering
            try:
                html_content = await page.content()
                logger.info(f"Got page HTML: {len(html_content)} chars")
            except Exception as e:
                logger.error(f"Failed to get HTML: {e}")
                return []

            # Now query for elements (should be in DOM now)
            result_elements = []
            try:
                # Re-query with fresh state
                result_elements = await page.query_selector_all('article[data-testid="result"]')
                logger.info(f"✓ Found {len(result_elements)} result articles")

                if len(result_elements) == 0:
                    # Fallback: Try li[data-layout="organic"]
                    li_elements = await page.query_selector_all('li[data-layout="organic"]')
                    logger.info(f"Fallback: Found {len(li_elements)} li[data-layout='organic']")

                    if len(li_elements) > 0:
                        # Query articles inside li elements
                        for li in li_elements[:max_results * 2]:
                            article = await li.query_selector('article[data-testid="result"]')
                            if article:
                                result_elements.append(article)
                        logger.info(f"✓ Extracted {len(result_elements)} articles from li elements")

            except Exception as e:
                logger.error(f"Error querying results: {e}")
                return []

            if len(result_elements) == 0:
                logger.warning("No results found after all attempts")
                return []

            for idx, article in enumerate(result_elements[:max_results * 2]):
                if len(results) >= max_results:
                    break

                try:
                    # Extract using EXACT selectors from USER's HTML
                    # Title link: a[data-testid="result-title-a"]
                    title_link = await article.query_selector('a[data-testid="result-title-a"]')
                    if not title_link:
                        logger.debug(f"Result {idx}: No title link found")
                        continue

                    # Get URL from title link
                    url = await title_link.get_attribute('href')
                    if not url:
                        logger.debug(f"Result {idx}: No URL")
                        continue

                    # Get title text from span inside link
                    title = ''
                    try:
                        title_span = await title_link.query_selector('span')
                        if title_span:
                            title = (await title_span.inner_text()).strip()
                        else:
                            title = (await title_link.inner_text()).strip()
                    except:
                        title = (await title_link.inner_text()).strip()

                    # Get snippet/description with EXACT selector from USER's HTML
                    snippet = ''
                    try:
                        # Exact: div[data-result="snippet"]
                        snippet_container = await article.query_selector('[data-result="snippet"]')
                        if snippet_container:
                            # Get text from span inside
                            snippet_spans = await snippet_container.query_selector_all('span')
                            snippet_parts = []
                            for span in snippet_spans:
                                text = (await span.inner_text()).strip()
                                if text and len(text) > 10:  # Skip short texts
                                    snippet_parts.append(text)
                            snippet = ' '.join(snippet_parts) if snippet_parts else (await snippet_container.inner_text()).strip()
                    except Exception as e:
                        logger.debug(f"Snippet extraction error: {e}")
                        pass

                    # Validate URL
                    if not url or url.startswith('#') or url.startswith('javascript:'):
                        continue

                    # Handle DuckDuckGo redirect links
                    if 'duckduckgo.com' in url:
                        if '/y.js?' in url:
                            # Extract real URL from redirect
                            try:
                                from urllib.parse import urlparse, parse_qs
                                parsed = urlparse(url)
                                query_params = parse_qs(parsed.query)
                                if 'uddg' in query_params:
                                    url = query_params['uddg'][0]
                                else:
                                    continue
                            except:
                                continue
                        else:
                            # Skip other DDG links
                            continue

                    # Must have valid URL
                    if url and len(url) > 10 and url.startswith('http'):
                        results.append({
                            'url': url,
                            'title': title if title else url,
                            'snippet': snippet
                        })
                        logger.info(f"  [{len(results)}] {title[:60]}")

                except Exception as e:
                    logger.debug(f"Error extracting result {idx}: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {str(e)}")
            return []
        finally:
            await page.close()

    async def _scrape_websites(self, url_data: List[Dict], max_results: int) -> List[Dict]:
        """
        Scrape business information from each website
        Now supports extracting MULTIPLE businesses per website (e.g. "Top 10" lists)
        with deduplication by phone number and business name

        Args:
            url_data: List of dicts with 'url', 'title', 'snippet'
            max_results: Max number of businesses to extract

        Returns:
            List of business data (deduplicated)
        """
        businesses = []
        seen_phones = set()  # Track unique phone numbers
        seen_names = set()   # Track unique business names (lowercase)

        for idx, item in enumerate(url_data):
            if len(businesses) >= max_results:
                break

            url = item['url']
            logger.info(f"[{idx+1}/{len(url_data)}] Scraping: {url[:80]}")

            try:
                # Extract ALL businesses from this website
                extracted_businesses = await self._extract_all_from_website(url, item)

                if extracted_businesses:
                    logger.info(f"  ✓ Extracted {len(extracted_businesses)} business(es) from page")

                    # Add each business with deduplication
                    for business in extracted_businesses:
                        # Check if we've reached max_results
                        if len(businesses) >= max_results:
                            break

                        # Deduplication check
                        phone = business.get('phone')
                        name = business.get('name', '').lower().strip()

                        # Skip if phone already seen
                        if phone and phone in seen_phones:
                            logger.debug(f"    ⊗ Skipped duplicate phone: {phone}")
                            continue

                        # Skip if business name already seen (avoid duplicates)
                        if name and name in seen_names and len(name) > 10:
                            logger.debug(f"    ⊗ Skipped duplicate name: {name[:50]}")
                            continue

                        # Add business
                        businesses.append(business)
                        if phone:
                            seen_phones.add(phone)
                        if name and len(name) > 10:
                            seen_names.add(name)

                        logger.info(f"    ✓ Added: {business.get('name', 'Unknown')[:50]}")

                else:
                    logger.debug(f"  ✗ No business data found")

            except Exception as e:
                logger.error(f"  ✗ Error: {str(e)}")
                continue

        logger.info(f"Total unique businesses after deduplication: {len(businesses)}")
        return businesses

    async def _extract_from_website(self, url: str, search_result: Dict) -> Optional[Dict]:
        """
        Extract business information from a single website

        Args:
            url: Website URL
            search_result: Dict with 'title', 'snippet' from search

        Returns:
            Business data dict or None
        """
        page = await self.context.new_page()

        try:
            # Go to website
            await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(2)

            # Get page content
            content = await page.content()

            # Extract business info
            data = {
                'name': search_result.get('title', ''),
                'phone': None,
                'email': None,
                'address': None,
                'website': url,
                'description': search_result.get('snippet', ''),
                'source': 'duckduckgo'
            }

            # Extract phone numbers
            phone = self._extract_phone(content)
            if phone:
                data['phone'] = phone

            # Extract emails
            email = self._extract_email(content)
            if email:
                data['email'] = email

            # Extract address (Vietnamese)
            address = self._extract_address(content)
            if address:
                data['address'] = address

            # Clean business name
            if not data['name']:
                # Try to get from page title
                title = await page.title()
                data['name'] = title[:200] if title else urlparse(url).netloc

            return data if (data['phone'] or data['email'] or data['address']) else None

        except Exception as e:
            logger.debug(f"Extract error for {url}: {str(e)}")
            return None
        finally:
            await page.close()

    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract FIRST Vietnamese phone number from text"""
        # Vietnamese phone patterns
        patterns = [
            r'(?:\+84|84|0)[\s\.\-]?[1-9]\d{1,2}[\s\.\-]?\d{3}[\s\.\-]?\d{3,4}',  # +84 xxx xxx xxx
            r'0[1-9]\d{8,9}',  # 0xxxxxxxxx
            r'\+84[1-9]\d{8,9}',  # +84xxxxxxxxx
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                phone = match.group(0)
                # Clean up
                phone = re.sub(r'[\s\.\-]', '', phone)
                return phone

        return None

    def _extract_all_phones(self, text: str) -> List[str]:
        """Extract ALL Vietnamese phone numbers from text"""
        phones = []
        seen = set()

        # Vietnamese phone patterns
        patterns = [
            r'(?:\+84|84|0)[\s\.\-]?[1-9]\d{1,2}[\s\.\-]?\d{3}[\s\.\-]?\d{3,4}',  # +84 xxx xxx xxx
            r'0[1-9]\d{8,9}',  # 0xxxxxxxxx
            r'\+84[1-9]\d{8,9}',  # +84xxxxxxxxx
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Clean up
                phone = re.sub(r'[\s\.\-]', '', match)
                # Deduplicate
                if phone not in seen and len(phone) >= 10:
                    phones.append(phone)
                    seen.add(phone)

        return phones

    def _extract_email(self, text: str) -> Optional[str]:
        """Extract FIRST email from text"""
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        match = re.search(pattern, text)
        if match:
            email = match.group(0)
            # Skip common generic emails
            if not any(x in email.lower() for x in ['example.com', 'test.com', 'domain.com']):
                return email
        return None

    def _extract_all_emails(self, text: str) -> List[str]:
        """Extract ALL emails from text"""
        emails = []
        seen = set()
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        matches = re.findall(pattern, text)

        for email in matches:
            # Skip generic emails
            if any(x in email.lower() for x in ['example.com', 'test.com', 'domain.com', 'sampleemail']):
                continue
            # Deduplicate
            if email.lower() not in seen:
                emails.append(email)
                seen.add(email.lower())

        return emails

    def _extract_all_addresses(self, text: str) -> List[str]:
        """Extract ALL Vietnamese addresses from text"""
        addresses = []
        seen = set()

        # Vietnamese address patterns
        patterns = [
            r'Địa chỉ[:\s]+([^\n<>]{20,200})',
            r'Address[:\s]+([^\n<>]{20,200})',
            r'\d+\s+(?:Phố|Đường|P\.|Quận|Q\.)[^\n<>]{10,150}',
            r'(?:Số|số)\s+\d+[,\s]+(?:Phố|Đường|phố|đường)[^\n<>]{10,150}',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Handle tuple results from groups
                address = match if isinstance(match, str) else match[0] if match else ''
                address = address.strip()
                # Clean HTML tags
                address = re.sub(r'<[^>]+>', '', address)
                # Validate length
                if 10 < len(address) < 300:
                    # Deduplicate
                    address_lower = address.lower()
                    if address_lower not in seen:
                        addresses.append(address)
                        seen.add(address_lower)

        return addresses

    def _extract_address(self, text: str) -> Optional[str]:
        """Extract Vietnamese address from text"""
        # Look for common Vietnamese address patterns
        patterns = [
            r'Địa chỉ[:\s]+([^\n<>]{20,200})',
            r'Address[:\s]+([^\n<>]{20,200})',
            r'\d+\s+(?:Phố|Đường|P\.|Quận|Q\.)[^\n<>]{10,150}',
            r'(?:Số|số)\s+\d+[,\s]+(?:Phố|Đường|phố|đường)[^\n<>]{10,150}',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                address = match.group(1) if match.lastindex else match.group(0)
                address = address.strip()
                # Clean HTML tags
                address = re.sub(r'<[^>]+>', '', address)
                if 10 < len(address) < 300:
                    return address

        return None

    async def _extract_all_from_website(self, url: str, search_result: Dict) -> List[Dict]:
        """
        Extract ALL businesses from a single website
        Useful for "Top 10" or listing pages

        Args:
            url: Website URL
            search_result: Dict with 'title', 'snippet' from search

        Returns:
            List of business data dicts
        """
        page = await self.context.new_page()
        businesses = []

        try:
            # Go to website
            await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(2)

            # Get page content
            content = await page.content()

            # Extract ALL contact info
            all_phones = self._extract_all_phones(content)
            all_emails = self._extract_all_emails(content)
            all_addresses = self._extract_all_addresses(content)

            logger.debug(f"  Found {len(all_phones)} phones, {len(all_emails)} emails, {len(all_addresses)} addresses")

            # Strategy: Create one business per unique phone number
            if all_phones:
                for idx, phone in enumerate(all_phones):
                    # Try to pair with email and address
                    email = all_emails[idx] if idx < len(all_emails) else None
                    address = all_addresses[idx] if idx < len(all_addresses) else None

                    # Generate business name from title or domain
                    if len(all_phones) == 1:
                        # Single business - use title as-is
                        name = search_result.get('title', '')
                    else:
                        # Multiple businesses - append index
                        base_name = search_result.get('title', urlparse(url).netloc)
                        name = f"{base_name} #{idx + 1}"

                    business = {
                        'name': name or urlparse(url).netloc,
                        'phone': phone,
                        'email': email,
                        'address': address,
                        'website': url,
                        'description': search_result.get('snippet', ''),
                        'source': 'duckduckgo'
                    }
                    businesses.append(business)

            # Fallback: If no phones, try to create at least one business with emails/addresses
            elif all_emails or all_addresses:
                email = all_emails[0] if all_emails else None
                address = all_addresses[0] if all_addresses else None

                business = {
                    'name': search_result.get('title', '') or urlparse(url).netloc,
                    'phone': None,
                    'email': email,
                    'address': address,
                    'website': url,
                    'description': search_result.get('snippet', ''),
                    'source': 'duckduckgo'
                }
                businesses.append(business)

            return businesses

        except Exception as e:
            logger.debug(f"Extract error for {url}: {str(e)}")
            return []
        finally:
            await page.close()


async def test_duckduckgo_scraper():
    """Test function"""
    scraper = DuckDuckGoScraper(headless=False)
    results = await scraper.scrape(
        keyword="cửa hàng hải sản",
        location="hà nội",
        max_results=5
    )

    print("\n" + "="*60)
    print(f"Found {len(results)} businesses")
    print("="*60)

    for idx, business in enumerate(results, 1):
        print(f"\n{idx}. {business['name']}")
        print(f"   Phone: {business.get('phone')}")
        print(f"   Email: {business.get('email')}")
        print(f"   Address: {business.get('address')}")
        print(f"   Website: {business['website'][:80]}")


if __name__ == '__main__':
    asyncio.run(test_duckduckgo_scraper())
