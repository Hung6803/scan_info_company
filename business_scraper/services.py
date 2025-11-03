"""
Business logic layer cho scraper
"""
import logging
from datetime import datetime
from typing import List, Dict
from asgiref.sync import sync_to_async
from .models import SearchQuery, Business
from .scraper import GoogleMapsScraper
from .duckduckgo_scraper import DuckDuckGoScraper
from .hsctvn_scraper import HSCTVNScraper

logger = logging.getLogger(__name__)


class BusinessScraperService:
    """Service class để xử lý business logic"""

    def __init__(self):
        self.google_scraper = GoogleMapsScraper()
        self.duckduckgo_scraper = DuckDuckGoScraper()
        self.hsctvn_scraper = HSCTVNScraper()

    async def scrape_and_save(
        self,
        keyword: str,
        location: str = None,
        max_results: int = 20
    ) -> SearchQuery:
        """
        Scrape dữ liệu từ Google Maps và lưu vào database

        Args:
            keyword: Từ khóa tìm kiếm
            location: Địa điểm
            max_results: Số lượng kết quả tối đa

        Returns:
            SearchQuery: Object search query đã được lưu
        """
        # Tạo search query record
        search_query = await sync_to_async(SearchQuery.objects.create)(
            keyword=keyword,
            location=location,
            source='google_maps',
            status='processing'
        )

        try:
            # Scrape dữ liệu
            businesses_data = await self.google_scraper.search_businesses(
                keyword=keyword,
                location=location,
                max_results=max_results
            )

            # Lưu businesses vào database
            saved_count = await self._save_businesses(search_query, businesses_data)

            # Cập nhật search query
            search_query.total_results = saved_count
            search_query.status = 'completed'
            await sync_to_async(search_query.save)()

            logger.info(f"Đã lưu {saved_count} doanh nghiệp cho keyword: {keyword}")

            return search_query

        except Exception as e:
            # Cập nhật trạng thái lỗi
            search_query.status = 'failed'
            search_query.error_message = str(e)
            await sync_to_async(search_query.save)()

            logger.error(f"Lỗi khi scrape và lưu dữ liệu: {str(e)}")
            raise

    async def scrape_duckduckgo_and_save(
        self,
        keyword: str,
        location: str = None,
        max_results: int = 10
    ) -> SearchQuery:
        """
        Scrape dữ liệu từ DuckDuckGo và lưu vào database

        Args:
            keyword: Từ khóa tìm kiếm
            location: Địa điểm
            max_results: Số lượng kết quả tối đa

        Returns:
            SearchQuery: Object search query đã được lưu
        """
        # Tạo search query record
        search_query = await sync_to_async(SearchQuery.objects.create)(
            keyword=keyword,
            location=location,
            source='duckduckgo',
            status='processing'
        )

        try:
            # Scrape dữ liệu từ DuckDuckGo
            businesses_data = await self.duckduckgo_scraper.scrape(
                keyword=keyword,
                location=location or "",
                max_results=max_results
            )

            # Lưu businesses vào database
            saved_count = await self._save_businesses(search_query, businesses_data)

            # Cập nhật search query
            search_query.total_results = saved_count
            search_query.status = 'completed'
            await sync_to_async(search_query.save)()

            logger.info(f"Đã lưu {saved_count} doanh nghiệp từ DuckDuckGo cho keyword: {keyword}")

            return search_query

        except Exception as e:
            # Cập nhật trạng thái lỗi
            search_query.status = 'failed'
            search_query.error_message = str(e)
            await sync_to_async(search_query.save)()

            logger.error(f"Lỗi khi scrape DuckDuckGo và lưu dữ liệu: {str(e)}")
            raise

    async def scrape_hsctvn_and_save(
        self,
        scrape_date: str,
        max_results: int = 100,
        max_pages: int = None
    ) -> SearchQuery:
        """
        Scrape dữ liệu từ HSCTVN và lưu vào database

        Args:
            scrape_date: Ngày scrape (format: YYYY-MM-DD)
            max_results: Số lượng kết quả tối đa
            max_pages: Số trang tối đa (None = tất cả)

        Returns:
            SearchQuery: Object search query đã được lưu
        """
        # Parse date
        date_obj = datetime.strptime(scrape_date, '%Y-%m-%d').date()

        # Tạo search query record
        search_query = await sync_to_async(SearchQuery.objects.create)(
            keyword=f"HSCTVN - {scrape_date}",
            location=None,
            source='hsctvn',
            status='processing'
        )

        try:
            # Scrape dữ liệu từ HSCTVN
            businesses_data = await self.hsctvn_scraper.scrape(
                scrape_date=date_obj,
                max_results=max_results,
                max_pages=max_pages
            )

            # Lưu businesses vào database
            saved_count = await self._save_businesses(search_query, businesses_data)

            # Cập nhật search query
            search_query.total_results = saved_count
            search_query.status = 'completed'
            await sync_to_async(search_query.save)()

            logger.info(f"Đã lưu {saved_count} doanh nghiệp từ HSCTVN cho ngày: {scrape_date}")

            return search_query

        except Exception as e:
            # Cập nhật trạng thái lỗi
            search_query.status = 'failed'
            search_query.error_message = str(e)
            await sync_to_async(search_query.save)()

            logger.error(f"Lỗi khi scrape HSCTVN và lưu dữ liệu: {str(e)}")
            raise

    async def _save_businesses(
        self,
        search_query: SearchQuery,
        businesses_data: List[Dict]
    ) -> int:
        """
        Lưu danh sách businesses vào database

        Args:
            search_query: Search query object
            businesses_data: Danh sách dữ liệu business

        Returns:
            int: Số lượng business đã lưu
        """
        saved_count = 0

        for business_data in businesses_data:
            try:
                # Parse issue_date if string
                issue_date = business_data.get('issue_date')
                if issue_date and isinstance(issue_date, str):
                    try:
                        from datetime import datetime
                        issue_date = datetime.strptime(issue_date, '%Y-%m-%d').date()
                    except Exception:
                        issue_date = None

                await sync_to_async(Business.objects.create)(
                    search_query=search_query,
                    name=business_data.get('name', ''),
                    tax_id=business_data.get('tax_id'),
                    legal_representative=business_data.get('legal_representative'),
                    phone=business_data.get('phone'),
                    email=business_data.get('email'),
                    address=business_data.get('address'),
                    issue_date=issue_date,
                    status=business_data.get('status'),
                    website=business_data.get('website'),
                    description=business_data.get('description'),
                    rating=business_data.get('rating'),
                    reviews_count=business_data.get('reviews_count', 0),
                    category=business_data.get('category'),
                    google_maps_url=business_data.get('google_maps_url'),
                    latitude=business_data.get('latitude'),
                    longitude=business_data.get('longitude'),
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"Lỗi khi lưu business {business_data.get('name')}: {str(e)}")
                continue

        return saved_count

    @staticmethod
    async def get_search_query(search_query_id: int) -> SearchQuery:
        """
        Lấy search query theo ID

        Args:
            search_query_id: ID của search query

        Returns:
            SearchQuery: Object search query
        """
        return await sync_to_async(
            SearchQuery.objects.prefetch_related('businesses').get
        )(id=search_query_id)

    @staticmethod
    async def get_all_search_queries() -> List[SearchQuery]:
        """
        Lấy tất cả search queries

        Returns:
            List[SearchQuery]: Danh sách search queries
        """
        return await sync_to_async(list)(
            SearchQuery.objects.all().order_by('-created_at')
        )

    @staticmethod
    async def get_all_businesses() -> List[Business]:
        """
        Lấy tất cả businesses

        Returns:
            List[Business]: Danh sách businesses
        """
        return await sync_to_async(list)(
            Business.objects.select_related('search_query').all().order_by('-created_at')
        )

    @staticmethod
    async def search_businesses_by_keyword(keyword: str) -> List[Business]:
        """
        Tìm kiếm businesses theo keyword trong database

        Args:
            keyword: Từ khóa tìm kiếm

        Returns:
            List[Business]: Danh sách businesses
        """
        return await sync_to_async(list)(
            Business.objects.filter(name__icontains=keyword).order_by('-created_at')
        )
