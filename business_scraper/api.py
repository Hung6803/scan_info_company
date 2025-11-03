"""
API endpoints sử dụng Django Ninja
"""
import logging
from typing import List
from ninja import Router
from django.shortcuts import get_object_or_404
from .models import SearchQuery, Business
from .schemas import (
    ScrapeRequestSchema,
    HSCTVNScrapeRequestSchema,
    ScrapeResponseSchema,
    SearchQuerySchema,
    SearchQueryDetailSchema,
    BusinessSchema,
    ErrorSchema
)
from .services import BusinessScraperService

logger = logging.getLogger(__name__)
router = Router()
scraper_service = BusinessScraperService()


@router.post("/scrape", response={200: ScrapeResponseSchema, 400: ErrorSchema, 500: ErrorSchema})
async def scrape_google_maps(request, payload: ScrapeRequestSchema):
    """
    Endpoint để scrape thông tin doanh nghiệp từ Google Maps

    Args:
        payload: ScrapeRequestSchema chứa keyword, location, max_results

    Returns:
        ScrapeResponseSchema: Kết quả scraping
    """
    try:
        search_query = await scraper_service.scrape_and_save(
            keyword=payload.keyword,
            location=payload.location,
            max_results=payload.max_results
        )

        return 200, {
            "search_query_id": search_query.id,
            "status": search_query.status,
            "total_results": search_query.total_results,
            "message": f"Đã scrape thành công {search_query.total_results} doanh nghiệp"
        }

    except Exception as e:
        logger.error(f"Lỗi khi scrape: {str(e)}")
        return 500, {
            "error": "Internal Server Error",
            "detail": str(e)
        }


@router.post("/scrape/duckduckgo", response={200: ScrapeResponseSchema, 400: ErrorSchema, 500: ErrorSchema})
async def scrape_duckduckgo(request, payload: ScrapeRequestSchema):
    """
    Endpoint để scrape thông tin doanh nghiệp từ DuckDuckGo

    Args:
        payload: ScrapeRequestSchema chứa keyword, location, max_results

    Returns:
        ScrapeResponseSchema: Kết quả scraping
    """
    try:
        search_query = await scraper_service.scrape_duckduckgo_and_save(
            keyword=payload.keyword,
            location=payload.location,
            max_results=payload.max_results if payload.max_results <= 20 else 10
        )

        return 200, {
            "search_query_id": search_query.id,
            "status": search_query.status,
            "total_results": search_query.total_results,
            "message": f"Đã scrape thành công {search_query.total_results} doanh nghiệp từ DuckDuckGo"
        }

    except Exception as e:
        logger.error(f"Lỗi khi scrape DuckDuckGo: {str(e)}")
        return 500, {
            "error": "Internal Server Error",
            "detail": str(e)
        }


@router.post("/scrape/hsctvn", response={200: ScrapeResponseSchema, 400: ErrorSchema, 500: ErrorSchema})
async def scrape_hsctvn(request, payload: HSCTVNScrapeRequestSchema):
    """
    Endpoint để scrape thông tin doanh nghiệp từ HSCTVN

    Args:
        payload: HSCTVNScrapeRequestSchema chứa date, max_results, max_pages

    Returns:
        ScrapeResponseSchema: Kết quả scraping
    """
    try:
        search_query = await scraper_service.scrape_hsctvn_and_save(
            scrape_date=payload.date,
            max_results=payload.max_results,
            max_pages=payload.max_pages
        )

        return 200, {
            "search_query_id": search_query.id,
            "status": search_query.status,
            "total_results": search_query.total_results,
            "message": f"Đã scrape thành công {search_query.total_results} doanh nghiệp từ HSCTVN"
        }

    except Exception as e:
        logger.error(f"Lỗi khi scrape HSCTVN: {str(e)}")
        return 500, {
            "error": "Internal Server Error",
            "detail": str(e)
        }


@router.get("/searches", response=List[SearchQuerySchema])
async def get_all_searches(request):
    """
    Lấy danh sách tất cả các lần tìm kiếm

    Returns:
        List[SearchQuerySchema]: Danh sách search queries
    """
    search_queries = await scraper_service.get_all_search_queries()
    return search_queries


@router.get("/searches/{search_query_id}", response={200: SearchQueryDetailSchema, 404: ErrorSchema})
async def get_search_detail(request, search_query_id: int):
    """
    Lấy chi tiết một lần tìm kiếm kèm danh sách businesses

    Args:
        search_query_id: ID của search query

    Returns:
        SearchQueryDetailSchema: Chi tiết search query
    """
    try:
        search_query = await scraper_service.get_search_query(search_query_id)
        return 200, search_query

    except SearchQuery.DoesNotExist:
        return 404, {
            "error": "Not Found",
            "detail": f"Search query với ID {search_query_id} không tồn tại"
        }


@router.get("/businesses", response=List[BusinessSchema])
async def get_all_businesses(request):
    """
    Lấy danh sách tất cả các doanh nghiệp

    Returns:
        List[BusinessSchema]: Danh sách businesses
    """
    businesses = await scraper_service.get_all_businesses()
    return businesses


@router.get("/businesses/search/{keyword}", response=List[BusinessSchema])
async def search_businesses(request, keyword: str):
    """
    Tìm kiếm doanh nghiệp theo keyword trong database

    Args:
        keyword: Từ khóa tìm kiếm

    Returns:
        List[BusinessSchema]: Danh sách businesses
    """
    businesses = await scraper_service.search_businesses_by_keyword(keyword)
    return businesses


@router.delete("/searches/{search_query_id}", response={200: dict, 404: ErrorSchema})
async def delete_search(request, search_query_id: int):
    """
    Xóa một search query và các businesses liên quan

    Args:
        search_query_id: ID của search query

    Returns:
        dict: Thông báo xóa thành công
    """
    from asgiref.sync import sync_to_async

    try:
        search_query = await sync_to_async(
            SearchQuery.objects.get
        )(id=search_query_id)

        await sync_to_async(search_query.delete)()

        return 200, {
            "message": f"Đã xóa search query {search_query_id} thành công"
        }

    except SearchQuery.DoesNotExist:
        return 404, {
            "error": "Not Found",
            "detail": f"Search query với ID {search_query_id} không tồn tại"
        }
