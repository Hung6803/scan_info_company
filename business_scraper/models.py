"""
Models cho việc lưu trữ thông tin doanh nghiệp từ Google Maps
"""
from django.db import models
from django.utils import timezone


class SearchQuery(models.Model):
    """Model lưu trữ lịch sử tìm kiếm"""
    keyword = models.CharField(max_length=255, verbose_name="Từ khóa tìm kiếm")
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="Địa điểm")
    source = models.CharField(
        max_length=20,
        choices=[
            ('google_maps', 'Google Maps'),
            ('duckduckgo', 'DuckDuckGo'),
            ('hsctvn', 'HSCTVN'),
        ],
        default='google_maps',
        verbose_name="Nguồn"
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Thời gian tìm kiếm")
    total_results = models.IntegerField(default=0, verbose_name="Tổng số kết quả")
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Đang chờ'),
            ('processing', 'Đang xử lý'),
            ('completed', 'Hoàn thành'),
            ('failed', 'Thất bại'),
        ],
        default='pending',
        verbose_name="Trạng thái"
    )
    error_message = models.TextField(blank=True, null=True, verbose_name="Thông báo lỗi")

    class Meta:
        db_table = 'search_queries'
        verbose_name = 'Truy vấn tìm kiếm'
        verbose_name_plural = 'Truy vấn tìm kiếm'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.keyword} - {self.location or 'No location'}"


class Business(models.Model):
    """Model lưu trữ thông tin doanh nghiệp"""
    search_query = models.ForeignKey(
        SearchQuery,
        on_delete=models.CASCADE,
        related_name='businesses',
        verbose_name="Truy vấn tìm kiếm"
    )
    name = models.CharField(max_length=500, verbose_name="Tên doanh nghiệp")
    tax_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="Mã số thuế")
    legal_representative = models.CharField(max_length=255, blank=True, null=True, verbose_name="Đại diện pháp luật")
    phone = models.CharField(max_length=50, blank=True, null=True, verbose_name="Số điện thoại")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    address = models.TextField(blank=True, null=True, verbose_name="Địa chỉ")
    issue_date = models.DateField(blank=True, null=True, verbose_name="Ngày cấp")
    status = models.CharField(max_length=100, blank=True, null=True, verbose_name="Trạng thái")
    website = models.URLField(max_length=1000, blank=True, null=True, verbose_name="Website")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả")
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        blank=True,
        null=True,
        verbose_name="Đánh giá"
    )
    reviews_count = models.IntegerField(default=0, verbose_name="Số lượng đánh giá")
    category = models.CharField(max_length=255, blank=True, null=True, verbose_name="Danh mục")
    google_maps_url = models.URLField(max_length=1000, blank=True, null=True, verbose_name="Link Google Maps")
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        blank=True,
        null=True,
        verbose_name="Vĩ độ"
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        blank=True,
        null=True,
        verbose_name="Kinh độ"
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Thời gian tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Thời gian cập nhật")

    class Meta:
        db_table = 'businesses'
        verbose_name = 'Doanh nghiệp'
        verbose_name_plural = 'Doanh nghiệp'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['tax_id']),
            models.Index(fields=['phone']),
            models.Index(fields=['email']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return self.name
