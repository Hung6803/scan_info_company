"""
URL configuration for the project.
"""
from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI
from business_scraper.api import router as business_router

# Create Ninja API instance
api = NinjaAPI(
    title="Google Maps Business Scraper API",
    version="1.0.0",
    description="API để scrape thông tin doanh nghiệp từ Google Maps và lưu vào database"
)

# Register routers
api.add_router("/business/", business_router)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
]
