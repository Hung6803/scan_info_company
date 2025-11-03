"""
HSCTVN.com Scraper
Scrape company information from https://hsctvn.com/

Features:
- Select specific date to scrape
- Auto pagination support
- Extract: company name, tax ID, address
- Fast scraping with Playwright
"""

import asyncio
import re
import logging
from datetime import date, datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HSCTVNScraper:
    """
    Scraper for hsctvn.com - Vietnamese company registry
    """

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize scraper

        Args:
            headless: Run browser in headless mode
            timeout: Timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
        self.base_url = "https://hsctvn.com"
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self._setup_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def _setup_browser(self):
        """Setup Playwright browser with stealth mode"""
        try:
            logger.info("Starting Playwright browser setup...")

            # Start Playwright and store the instance
            self.playwright = await async_playwright().start()
            logger.info("Playwright started successfully")

            # Launch browser
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            logger.info("Browser launched successfully")

            # Create browser context
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            logger.info("Browser context created successfully")

            # Remove webdriver detection
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            logger.info("Browser setup complete - Ready to scrape")

        except Exception as e:
            logger.error(f"Failed to setup browser: {str(e)}")
            # Clean up any partial initialization
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            raise RuntimeError(f"Browser setup failed: {str(e)}") from e

    async def close(self):
        """Close browser and cleanup resources"""
        try:
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            logger.info("Browser closed and resources cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    async def scrape(
        self,
        scrape_date: date = None,
        max_results: int = 100,
        max_pages: Optional[int] = None
    ) -> List[Dict]:
        """
        Scrape companies from hsctvn.com for a specific date

        Args:
            scrape_date: Date to scrape (default: today)
            max_results: Maximum number of companies to scrape
            max_pages: Maximum number of pages to scrape (None = all pages)

        Returns:
            List of company data dicts
        """
        if not scrape_date:
            scrape_date = date.today()

        # Format date
        day = scrape_date.day
        month = scrape_date.month
        year = scrape_date.year

        logger.info("="*60)
        logger.info("=== HSCTVN SCRAPER ===")
        logger.info(f"Date: {day}/{month}/{year}")
        logger.info(f"Max results: {max_results}")
        logger.info("="*60)

        # Setup browser if not already done or if browser is disconnected
        if not self.browser or not self.browser.is_connected():
            # Close old browser if exists but disconnected
            if self.browser:
                logger.info("Browser disconnected, cleaning up and reinitializing...")
                await self.close()
            await self._setup_browser()

        # Validate browser and context are ready
        if not self.browser or not self.context:
            raise RuntimeError("Browser initialization failed - browser or context is None")

        # Build URL
        url = f"{self.base_url}/ngay-{day}/{month}/{year}"
        logger.info(f"URL: {url}")

        # Get first page to determine total companies and pages
        page = await self.context.new_page()
        companies = []

        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
            await asyncio.sleep(2)  # Wait for content to render

            # Wait for company list to appear
            try:
                await page.wait_for_selector('li:has(h3 > a)', timeout=10000)
            except Exception:
                logger.warning("Could not find company list selector")

            # Take screenshot for debugging
            await page.screenshot(path='hsctvn_debug.png')
            logger.info("Screenshot saved: hsctvn_debug.png")

            # Get total companies count
            total_companies = await self._get_total_companies(page)
            logger.info(f"Total companies on {day}/{month}/{year}: {total_companies}")

            if total_companies == 0:
                logger.warning("No companies found for this date")
                return []

            # Calculate total pages (assuming ~12 companies per page based on 784/66)
            companies_per_page = 12
            total_pages = (total_companies + companies_per_page - 1) // companies_per_page

            if max_pages:
                total_pages = min(total_pages, max_pages)

            # Calculate pages needed to reach max_results
            pages_needed = min(total_pages, (max_results + companies_per_page - 1) // companies_per_page)

            logger.info(f"Total pages: {total_pages}")
            logger.info(f"Will scrape: {pages_needed} pages")

            # Scrape first page
            page_companies = await self._scrape_page(page)
            companies.extend(page_companies)
            logger.info(f"[Page 1/{pages_needed}] Extracted {len(page_companies)} companies")

            # Scrape remaining pages
            for page_num in range(2, pages_needed + 1):
                if len(companies) >= max_results:
                    break

                page_url = f"{url}/page-{page_num}"
                await page.goto(page_url, wait_until='domcontentloaded', timeout=self.timeout)
                await asyncio.sleep(0.5)

                page_companies = await self._scrape_page(page)
                companies.extend(page_companies)
                logger.info(f"[Page {page_num}/{pages_needed}] Extracted {len(page_companies)} companies")

            # Trim to max_results
            companies = companies[:max_results]

            logger.info("="*60)
            logger.info(f"✓ Scraped {len(companies)} companies from {pages_needed} pages")
            logger.info("="*60)

            return companies

        except Exception as e:
            logger.error(f"Scraping error: {str(e)}")
            raise
        finally:
            await page.close()
            # Close browser after scraping to prevent connection issues on next request
            logger.info("Cleaning up browser resources after scraping...")
            await self.close()

    async def _get_total_companies(self, page: Page) -> int:
        """
        Extract total number of companies from page heading

        Args:
            page: Playwright page

        Returns:
            Total number of companies
        """
        try:
            # Look for heading like "tìm thấy 784 hồ sơ công ty | trang 1"
            # or "tìm thấy <label>1,021</label> hồ sơ công ty | trang 1"
            content = await page.content()

            # Log content for debugging
            logger.debug(f"Page content length: {len(content)} chars")

            # Try multiple patterns - handle numbers with commas (1,021) or dots (1.021)
            patterns = [
                r'tìm thấy\s+<label>([\d,\.]+)</label>\s+hồ sơ',  # "tìm thấy <label>1,021</label> hồ sơ"
                r'tìm thấy\s+([\d,\.]+)\s+hồ sơ\s+công ty',  # "tìm thấy 1,021 hồ sơ công ty"
                r'tìm thấy\s+([\d,\.]+)\s+hồ sơ',  # "tìm thấy 1,021 hồ sơ"
                r'([\d,\.]+)\s+hồ sơ\s+công ty',  # "1,021 hồ sơ công ty"
                r'<h\d+[^>]*>.*?([\d,\.]+)\s+hồ sơ.*?</h\d+>',  # In heading tag
            ]

            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    # Extract number and remove commas/dots
                    number_str = match.group(1).replace(',', '').replace('.', '')
                    count = int(number_str)
                    logger.info(f"Found company count: {count} (original: {match.group(1)})")
                    return count

            # If regex fails, try to find via text content
            try:
                text_content = await page.inner_text('body')
                match = re.search(r'tìm thấy\s+([\d,\.]+)\s+hồ sơ', text_content, re.IGNORECASE)
                if match:
                    number_str = match.group(1).replace(',', '').replace('.', '')
                    count = int(number_str)
                    logger.info(f"Found company count in page text: {count}")
                    return count
            except Exception:
                pass

            logger.warning("Could not find total companies count")
            # Save content to file for debugging
            with open('hsctvn_debug_content.html', 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info("Saved page content to hsctvn_debug_content.html for debugging")
            return 0

        except Exception as e:
            logger.error(f"Error getting total companies: {str(e)}")
            return 0

    async def _scrape_page(self, page: Page) -> List[Dict]:
        """
        Scrape companies from a single page

        Args:
            page: Playwright page

        Returns:
            List of company data dicts
        """
        companies = []

        try:
            # Find all <li> elements containing company data
            li_elements = await page.query_selector_all('li:has(h3 > a)')
            logger.debug(f"Found {len(li_elements)} li elements with h3>a")

            # If no elements found, try simpler selector
            if len(li_elements) == 0:
                li_elements = await page.query_selector_all('li')
                logger.debug(f"Found {len(li_elements)} li elements (all)")

            # Debug: Save first li element HTML
            if len(li_elements) > 0:
                first_li_html = await li_elements[0].inner_html()
                with open('hsctvn_first_li.html', 'w', encoding='utf-8') as f:
                    f.write(first_li_html)
                logger.info("Saved first li element HTML to hsctvn_first_li.html")

            for idx, li in enumerate(li_elements, 1):
                try:
                    company_data = await self._extract_company_from_li(li)
                    if company_data:
                        companies.append(company_data)
                        logger.debug(f"  [{idx}] ✓ Extracted: {company_data.get('name', '')[:50]}")
                    else:
                        logger.debug(f"  [{idx}] ✗ No data extracted")
                except Exception as e:
                    logger.debug(f"  [{idx}] ✗ Error extracting company: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping page: {str(e)}")

        return companies

    async def _extract_company_from_li(self, li_element) -> Optional[Dict]:
        """
        Extract company data from <li> element

        HTML structure:
        <li>
          <h3><a href="...">COMPANY NAME</a></h3>
          <div>
            <em>Địa chỉ:</em> ADDRESS...
            <br>Mã số thuế: <a href="...">TAX_ID</a>
          </div>
        </li>

        Args:
            li_element: Playwright element

        Returns:
            Dict with company data or None
        """
        try:
            # Extract company name from <h3><a>
            name_elem = await li_element.query_selector('h3 a')
            if not name_elem:
                logger.debug("No h3 > a found in li element")
                return None

            name = (await name_elem.inner_text()).strip()
            company_url = await name_elem.get_attribute('href')

            if not name:
                logger.debug("Empty company name")
                return None

            # Extract from <p> or <div> element
            content_elem = await li_element.query_selector('p')
            if not content_elem:
                content_elem = await li_element.query_selector('div')

            if not content_elem:
                logger.debug(f"No <p> or <div> element found for: {name[:30]}")
                return None

            content_text = await content_elem.inner_text()
            logger.debug(f"Content text for {name[:30]}: {content_text[:100]}")

            # Extract address (after "Địa chỉ:")
            address = None
            address_match = re.search(r'Địa chỉ:\s*(.+?)(?:\n|Mã số thuế)', content_text, re.DOTALL)
            if address_match:
                address = address_match.group(1).strip()

            # Extract tax ID (after "Mã số thuế:")
            tax_id = None
            tax_id_match = re.search(r'Mã số thuế:\s*(\d+)', content_text)
            if tax_id_match:
                tax_id = tax_id_match.group(1).strip()

            # Validate required fields
            if not name or not tax_id:
                logger.debug(f"Missing required field - name: {bool(name)}, tax_id: {bool(tax_id)}")
                return None

            # Build basic company data
            company_data = {
                'name': name,
                'tax_id': tax_id,
                'address': address,
                'website': urljoin(self.base_url, company_url) if company_url else None,
                'source': 'hsctvn'
            }

            # Navigate to detail page to get more info
            if company_url:
                detail_url = urljoin(self.base_url, company_url)
                detail_data = await self._scrape_detail_page(detail_url)
                if detail_data:
                    company_data.update(detail_data)

            return company_data

        except Exception as e:
            logger.debug(f"Error extracting company data: {str(e)}")
            return None

    async def _scrape_detail_page(self, detail_url: str) -> Optional[Dict]:
        """
        Navigate to detail page and extract additional information

        Detail page structure:
        <li>Mã số thuế: 4202041214</li>
        <li>Đại diện pháp luật: <a>Nguyễn Sỹ Văn</a></li>
        <li>Điện thoại: 0901030676</li>
        <li>Ngày cấp: <a>21/10/2025</a></li>
        <li>Trạng thái: Đang Hoạt Động</li>

        Args:
            detail_url: URL to company detail page

        Returns:
            Dict with additional company data or None
        """
        # Validate context before creating page
        if not self.context:
            logger.error("Browser context is None - cannot create new page")
            return None

        page = await self.context.new_page()

        try:
            logger.debug(f"  Fetching detail page: {detail_url[:60]}...")
            await page.goto(detail_url, wait_until='domcontentloaded', timeout=self.timeout)
            await asyncio.sleep(0.5)

            # Get page text content
            body_text = await page.inner_text('body')

            # Extract fields from <li> elements
            detail_data = {}

            # Phone (Điện thoại)
            phone_match = re.search(r'Điện thoại:\s*([0-9\s\-\+]+)', body_text, re.IGNORECASE)
            if phone_match:
                phone = phone_match.group(1).strip()
                detail_data['phone'] = re.sub(r'\s+', '', phone)  # Remove spaces

            # Legal representative (Đại diện pháp luật)
            legal_rep_match = re.search(r'Đại diện pháp luật:\s*([^\n]+)', body_text, re.IGNORECASE)
            if legal_rep_match:
                detail_data['legal_representative'] = legal_rep_match.group(1).strip()

            # Issue date (Ngày cấp) - format: 21/10/2025
            issue_date_match = re.search(r'Ngày cấp:\s*(\d{1,2}/\d{1,2}/\d{4})', body_text, re.IGNORECASE)
            if issue_date_match:
                date_str = issue_date_match.group(1).strip()
                # Parse date
                try:
                    from datetime import datetime
                    parsed_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                    detail_data['issue_date'] = parsed_date.isoformat()  # YYYY-MM-DD format
                except Exception:
                    logger.debug(f"  Could not parse date: {date_str}")

            # Status (Trạng thái)
            status_match = re.search(r'Trạng thái:\s*([^\n]+)', body_text, re.IGNORECASE)
            if status_match:
                detail_data['status'] = status_match.group(1).strip()

            # Full address from detail page (more complete than list page)
            address_match = re.search(r'Địa chỉ(?:\s+thuế)?:\s*([^\n]{20,300})', body_text, re.IGNORECASE)
            if address_match:
                full_address = address_match.group(1).strip()
                if len(full_address) > 20:  # Only update if more detailed
                    detail_data['address'] = full_address

            logger.debug(f"  ✓ Detail extracted: phone={bool(detail_data.get('phone'))}, legal_rep={bool(detail_data.get('legal_representative'))}")

            return detail_data

        except Exception as e:
            logger.debug(f"  ✗ Error scraping detail page: {str(e)}")
            return None
        finally:
            await page.close()


async def test_hsctvn_scraper():
    """Test function"""
    scraper = HSCTVNScraper(headless=False)

    # Test with specific date
    test_date = date(2025, 10, 21)

    results = await scraper.scrape(
        scrape_date=test_date,
        max_results=30,
        max_pages=3
    )

    print("\n" + "="*60)
    print(f"Found {len(results)} companies")
    print("="*60)

    for idx, company in enumerate(results[:10], 1):
        print(f"\n{idx}. {company['name']}")
        print(f"   Tax ID: {company.get('tax_id')}")
        print(f"   Address: {company.get('address', 'N/A')[:80]}")
        if company.get('website'):
            print(f"   Website: {company['website'][:80]}")

    await scraper.close()


if __name__ == '__main__':
    asyncio.run(test_hsctvn_scraper())
