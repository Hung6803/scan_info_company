"""
Admin configuration cho Business Scraper
"""
from django.contrib import admin
from .models import SearchQuery, Business


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ['keyword', 'location', 'total_results', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['keyword', 'location']
    readonly_fields = ['created_at']
    ordering = ['-created_at']


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'address', 'rating', 'created_at']
    list_filter = ['created_at', 'category']
    search_fields = ['name', 'phone', 'email', 'address']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('search_query', 'name', 'category')
        }),
        ('Thông tin liên hệ', {
            'fields': ('phone', 'email', 'website', 'address')
        }),
        ('Đánh giá', {
            'fields': ('rating', 'reviews_count')
        }),
        ('Vị trí', {
            'fields': ('latitude', 'longitude', 'google_maps_url')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
