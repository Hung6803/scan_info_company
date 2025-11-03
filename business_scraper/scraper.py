"""
Google Maps Scraper V4.0 - EXACT selectors từ HTML thực tế
Based on actual Google Maps HTML structure
"""
import re
import asyncio
import logging
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout
from django.conf import settings

logger = logging.getLogger(__name__)


class GoogleMapsScraper:
    """Scraper V4.0 - Exact selectors from real HTML"""

    def __init__(self):
        self.headless = settings.SCRAPER_HEADLESS
        self.timeout = settings.SCRAPER_TIMEOUT
        self.max_results = settings.MAX_RESULTS_PER_SEARCH

    async def search_businesses(
        self,
        keyword: str,
        location: Optional[str] = None,
        max_results: int = 20
    ) -> List[Dict]:
        """Tìm kiếm doanh nghiệp"""

        if max_results > self.max_results:
            max_results = self.max_results

        search_query = f"{keyword}"
        if location:
            search_query += f" {location}"

        logger.info(f"=== SCRAPER V4.0 ===")
        logger.info(f"Search: {search_query}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                locale='vi-VN'
            )
            page = await context.new_page()

            try:
                url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
                logger.info(f"URL: {url}")

                await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
                await asyncio.sleep(5)

                businesses = await self._extract_businesses(page, max_results)

                logger.info(f"✓ Total found: {len(businesses)}")
                return businesses

            except Exception as e:
                logger.error(f"Error: {str(e)}", exc_info=True)
                raise
            finally:
                await browser.close()

    async def _extract_businesses(self, page: Page, max_results: int) -> List[Dict]:
        """Extract businesses với EXACT selectors"""

        businesses = []
        seen_names = set()

        # Wait for feed
        try:
            await page.wait_for_selector('div[role="feed"]', timeout=10000)
            logger.info("✓ Feed found")
        except:
            logger.error("✗ Feed not found")
            return businesses

        # Scroll để load items
        await self._scroll_feed(page)
        await asyncio.sleep(3)

        # Get business items - EXACT selector: div.Nv2PK
        business_items = await page.query_selector_all('div.Nv2PK')
        logger.info(f"✓ Found {len(business_items)} business items (div.Nv2PK)")

        if not business_items:
            # Fallback: try a.hfpxzc
            links = await page.query_selector_all('a.hfpxzc')
            logger.info(f"Fallback: Found {len(links)} links (a.hfpxzc)")

            # Filter links to get parent divs
            for link in links:
                parent = await link.evaluate_handle('el => el.closest("div.Nv2PK")')
                if parent:
                    business_items.append(parent)

        # Extract from each item
        for idx, item in enumerate(business_items[:max_results * 2]):
            if len(businesses) >= max_results:
                break

            try:
                # Get link element
                link = await item.query_selector('a.hfpxzc')
                if not link:
                    continue

                # Get aria-label for logging
                aria_label = await link.get_attribute('aria-label')
                if not aria_label:
                    continue

                # Skip sponsored items
                sponsored = await item.query_selector('.jHLihd')
                if sponsored:
                    logger.debug(f"Skip sponsored: {aria_label[:40]}")
                    continue

                logger.info(f"[{idx+1}] Clicking: {aria_label[:60]}")

                # Scroll and click
                await link.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                await link.click()
                await asyncio.sleep(3)

                # Extract details
                business_data = await self._extract_details(page)

                if business_data and business_data.get('name'):
                    name = business_data['name']

                    # Skip UI elements
                    if name in ['Kết quả', 'Results']:
                        continue

                    if name not in seen_names:
                        businesses.append(business_data)
                        seen_names.add(name)
                        logger.info(f"✓ [{len(businesses)}/{max_results}] {name}")

            except Exception as e:
                logger.error(f"Error item {idx}: {str(e)}")
                continue

            # Scroll and reload
            if (idx + 1) % 5 == 0 and len(businesses) < max_results:
                await self._scroll_feed(page)
                await asyncio.sleep(2)

        return businesses

    async def _extract_details(self, page: Page) -> Optional[Dict]:
        """Extract chi tiết với EXACT selectors"""

        data = {
            'name': '',
            'phone': None,
            'email': None,
            'address': None,
            'website': None,
            'rating': None,
            'reviews_count': 0,
            'category': None,
            'google_maps_url': None,
            'latitude': None,
            'longitude': None,
        }

        try:
            # URL
            data['google_maps_url'] = page.url

            # Coords
            coords = self._extract_coords(page.url)
            if coords:
                data['latitude'], data['longitude'] = coords

            # Wait a bit
            await asyncio.sleep(1)

            # NAME - Multiple strategies based on REAL HTML
            try:
                # Strategy 1: Try h1 (common in some detail panels)
                name_elem = await page.query_selector('h1.DUwDvf')
                if name_elem:
                    name_text = (await name_elem.inner_text()).strip()
                    if name_text and name_text not in ['Kết quả', 'Results']:
                        data['name'] = name_text

                # Strategy 2: Parse from detail panel aria-label
                # <div class="m6QErb" role="region" aria-label="Thông tin về [NAME]">
                if not data['name']:
                    panel = await page.query_selector('div.m6QErb[role="region"]')
                    if panel:
                        aria_label = await panel.get_attribute('aria-label')
                        if aria_label and 'Thông tin về' in aria_label:
                            # Extract name after "Thông tin về "
                            name_text = aria_label.replace('Thông tin về', '').strip()
                            if name_text and name_text not in ['Kết quả', 'Results']:
                                data['name'] = name_text

                # Strategy 3: From link we clicked (stored in aria-label)
                # We can pass this from the calling function

            except Exception as e:
                logger.debug(f"Name extraction error: {e}")
                pass

            if not data['name']:
                logger.warning("Could not extract business name")
                return None

            # CATEGORY - button with jsaction*="category"
            try:
                cat = await page.query_selector('button[jsaction*="category"]')
                if cat:
                    cat_text = (await cat.inner_text()).strip()
                    if cat_text and 'Cập nhật' not in cat_text:
                        data['category'] = cat_text
            except:
                pass

            # RATING - span.ZkP5Je with role="img"
            try:
                rating_elem = await page.query_selector('span.ZkP5Je[role="img"]')
                if rating_elem:
                    aria = await rating_elem.get_attribute('aria-label')
                    if aria:
                        # Extract rating: "4,9 sao 31 bài đánh giá"
                        rating_match = re.search(r'([\d,\.]+)\s*sao', aria)
                        if rating_match:
                            data['rating'] = float(rating_match.group(1).replace(',', '.'))

                        # Extract reviews: "31 bài đánh giá"
                        reviews_match = re.search(r'([\d\.]+)\s*bài đánh giá', aria)
                        if reviews_match:
                            data['reviews_count'] = int(reviews_match.group(1).replace('.', ''))
            except:
                pass

            # ADDRESS - EXACT selector from real HTML
            # <button data-item-id="address"><div class="Io6YTe">ADDRESS</div></button>
            try:
                addr_elem = await page.query_selector('button[data-item-id="address"] div.Io6YTe')
                if addr_elem:
                    addr_text = (await addr_elem.inner_text()).strip()
                    if addr_text and len(addr_text) > 5:
                        data['address'] = addr_text
            except Exception as e:
                logger.debug(f"Address extraction error: {e}")
                pass

            # PHONE - EXACT selector from real HTML
            # <button data-item-id="phone:tel:0369626262"><div class="Io6YTe">+84 369 626 262</div></button>
            try:
                phone_elem = await page.query_selector('button[data-item-id^="phone"] div.Io6YTe')
                if phone_elem:
                    phone_text = (await phone_elem.inner_text()).strip()
                    # Validate it looks like a phone number
                    if phone_text and re.search(r'[\d\+\s\-\(\)]{8,}', phone_text):
                        data['phone'] = phone_text
            except Exception as e:
                logger.debug(f"Phone extraction error: {e}")
                pass

            # WEBSITE - a[data-item-id="authority"]
            try:
                web = await page.query_selector('a[data-item-id="authority"]')
                if web:
                    href = await web.get_attribute('href')
                    if href and 'google.com' not in href:
                        data['website'] = href
            except:
                pass

        except Exception as e:
            logger.error(f"Extract details error: {str(e)}")

        return data if data.get('name') else None

    async def _scroll_feed(self, page: Page):
        """Scroll results feed"""
        try:
            await page.evaluate("""
                () => {
                    const feed = document.querySelector('div[role="feed"]');
                    if (feed) {
                        feed.scrollBy(0, 1500);
                    }
                }
            """)
        except:
            pass

    def _extract_coords(self, url: str) -> Optional[tuple]:
        """Extract coordinates from URL"""
        try:
            match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
            if match:
                return (float(match.group(1)), float(match.group(2)))

            match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', url)
            if match:
                return (float(match.group(1)), float(match.group(2)))
        except:
            pass
        return None


def extract_email_from_website(website: str) -> Optional[str]:
    return None
