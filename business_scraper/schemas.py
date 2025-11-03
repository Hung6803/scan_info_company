"""
Pydantic schemas cho API
"""
from typing import Optional, List
from datetime import datetime, date
from ninja import Schema
from decimal import Decimal


class BusinessSchema(Schema):
    """Schema cho thông tin doanh nghiệp"""
    id: int
    name: str
    tax_id: Optional[str] = None
    legal_representative: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    issue_date: Optional[date] = None
    status: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    rating: Optional[Decimal] = None
    reviews_count: int = 0
    category: Optional[str] = None
    google_maps_url: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class SearchQuerySchema(Schema):
    """Schema cho truy vấn tìm kiếm"""
    id: int
    keyword: str
    location: Optional[str] = None
    source: str = 'google_maps'
    created_at: datetime
    total_results: int = 0
    status: str


class SearchQueryDetailSchema(SearchQuerySchema):
    """Schema chi tiết cho truy vấn tìm kiếm kèm danh sách doanh nghiệp"""
    businesses: List[BusinessSchema] = []


class ScrapeRequestSchema(Schema):
    """Schema cho yêu cầu scrape"""
    keyword: str
    location: Optional[str] = None
    max_results: int = 20


class HSCTVNScrapeRequestSchema(Schema):
    """Schema cho yêu cầu scrape từ HSCTVN"""
    date: str  # Format: YYYY-MM-DD
    max_results: int = 100
    max_pages: Optional[int] = None


class ScrapeResponseSchema(Schema):
    """Schema cho kết quả scrape"""
    search_query_id: int
    status: str
    total_results: int
    message: str


class ErrorSchema(Schema):
    """Schema cho thông báo lỗi"""
    error: str
    detail: Optional[str] = None
