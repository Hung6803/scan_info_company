# Business Scraper API

Hệ thống scraping thông tin doanh nghiệp từ nhiều nguồn với Django Ninja API.

## Tổng quan

Ứng dụng cung cấp 3 scraper chuyên biệt:
- **Google Maps**: Tìm kiếm doanh nghiệp theo từ khóa và địa điểm
- **DuckDuckGo**: Tìm kiếm và trích xuất thông tin từ các website
- **HSCTVN**: Theo dõi công ty mới thành lập theo ngày

## Tính năng chính

### 🗺️ Google Maps Scraper
- Tìm kiếm doanh nghiệp theo từ khóa + địa điểm
- Trích xuất: tên, số điện thoại, email, địa chỉ, đánh giá, website
- Lấy tọa độ GPS (latitude/longitude)
- Hỗ trợ lọc theo rating và review count

### 🔍 DuckDuckGo Scraper
- Tìm kiếm trên DuckDuckGo
- Trích xuất nhiều businesses từ một trang (listing pages)
- Deduplication tự động (theo phone, name)
- Lấy thông tin: phone, email, address từ website

### 🏢 HSCTVN Scraper
- Scrape công ty mới thành lập theo ngày
- Auto pagination (crawl nhiều trang tự động)
- Trích xuất đầy đủ: mã số thuế, phone, đại diện pháp luật, ngày cấp, trạng thái
- 100% coverage cho tất cả fields

## Yêu cầu hệ thống

- **Python**: 3.12+
- **PostgreSQL**: 14+
- **Docker & Docker Compose**: (khuyến nghị)

## Cài đặt nhanh

### 1. Clone và setup môi trường

```bash
# Clone project
cd scan_info_company_map

# Tạo virtual environment
python -m venv .venv

# Kích hoạt venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt

# Cài đặt Playwright browsers
playwright install chromium
```

### 2. Setup Database với Docker

```bash
# Start PostgreSQL
docker-compose up -d

# Kiểm tra PostgreSQL running
docker-compose ps
```

### 3. Cấu hình môi trường

```bash
# Copy .env.example
cp .env.example .env

# File .env đã được cấu hình sẵn cho Docker
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/business_scraper_db
```

### 4. Chạy migrations

```bash
python manage.py migrate

# Tạo superuser để truy cập admin
python manage.py createsuperuser
```

### 5. Start server

```bash
# Windows
run.bat

# Linux/Mac
./run.sh

# Hoặc
python manage.py runserver
```

Server chạy tại: **http://localhost:8000**

## API Documentation

### 📚 Interactive Docs

- **Swagger UI**: http://localhost:8000/api/docs
- **OpenAPI Schema**: http://localhost:8000/api/openapi.json

### 🔗 Endpoints chính

#### 1. Google Maps Scraper

```bash
POST /api/business/scrape
```

**Request:**
```json
{
  "keyword": "nhà hàng hải sản",
  "location": "Hà Nội",
  "max_results": 20
}
```

**Response:**
```json
{
  "search_query_id": 1,
  "status": "completed",
  "total_results": 18,
  "message": "Đã scrape thành công 18 doanh nghiệp"
}
```

#### 2. DuckDuckGo Scraper

```bash
POST /api/business/scrape/duckduckgo
```

**Request:**
```json
{
  "keyword": "cửa hàng điện thoại",
  "location": "Hồ Chí Minh",
  "max_results": 15
}
```

**Response:**
```json
{
  "search_query_id": 2,
  "status": "completed",
  "total_results": 15,
  "message": "Đã scrape thành công 15 doanh nghiệp từ DuckDuckGo"
}
```

#### 3. HSCTVN Scraper

```bash
POST /api/business/scrape/hsctvn
```

**Request:**
```json
{
  "date": "2025-10-21",
  "max_results": 100,
  "max_pages": 10
}
```

**Response:**
```json
{
  "search_query_id": 3,
  "status": "completed",
  "total_results": 100,
  "message": "Đã scrape thành công 100 doanh nghiệp từ HSCTVN"
}
```

#### 4. Lấy kết quả scraping

```bash
GET /api/business/searches/{search_query_id}
```

**Response:**
```json
{
  "id": 1,
  "keyword": "nhà hàng hải sản",
  "location": "Hà Nội",
  "source": "google_maps",
  "total_results": 18,
  "status": "completed",
  "created_at": "2025-10-27T10:30:00Z",
  "businesses": [
    {
      "id": 1,
      "name": "Nhà Hàng Hải Sản ABC",
      "phone": "0901234567",
      "email": "contact@abc.com",
      "address": "123 Đường ABC, Hà Nội",
      "website": "https://abc.com",
      "rating": 4.5,
      "reviews_count": 120
    }
  ]
}
```

#### 5. Lấy tất cả searches

```bash
GET /api/business/searches
```

#### 6. Lấy tất cả businesses

```bash
GET /api/business/businesses
```

#### 7. Tìm kiếm trong database

```bash
GET /api/business/businesses/search/{keyword}
```

#### 8. Xóa search query

```bash
DELETE /api/business/searches/{search_query_id}
```

## Ví dụ sử dụng

### Ví dụ 1: Tìm nhà hàng với curl

```bash
curl -X POST http://localhost:8000/api/business/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "nhà hàng",
    "location": "Hà Nội",
    "max_results": 20
  }'
```

### Ví dụ 2: Tìm công ty mới thành lập

```bash
curl -X POST http://localhost:8000/api/business/scrape/hsctvn \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-10-21",
    "max_results": 50
  }'
```

### Ví dụ 3: Lấy kết quả

```bash
curl http://localhost:8000/api/business/searches/1
```

## Database Models

### SearchQuery

Lưu lịch sử tìm kiếm:

```python
class SearchQuery(models.Model):
    keyword = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True, null=True)
    source = models.CharField(max_length=20)  # google_maps, duckduckgo, hsctvn
    total_results = models.IntegerField(default=0)
    status = models.CharField(max_length=20)  # pending, processing, completed, failed
    created_at = models.DateTimeField(auto_now_add=True)
```

### Business

Lưu thông tin doanh nghiệp:

```python
class Business(models.Model):
    search_query = models.ForeignKey(SearchQuery)
    name = models.CharField(max_length=500)
    tax_id = models.CharField(max_length=50)  # Mã số thuế
    legal_representative = models.CharField(max_length=255)  # Đại diện pháp luật
    phone = models.CharField(max_length=50)
    email = models.EmailField()
    address = models.TextField()
    issue_date = models.DateField()  # Ngày cấp
    status = models.CharField(max_length=100)  # Trạng thái hoạt động
    website = models.URLField(max_length=1000)
    description = models.TextField()
    rating = models.DecimalField(max_digits=2, decimal_places=1)
    reviews_count = models.IntegerField()
    category = models.CharField(max_length=255)
    google_maps_url = models.URLField(max_length=1000)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    created_at = models.DateTimeField(auto_now_add=True)
```

## Cấu trúc Project

```
scan_info_company_map/
├── config/                      # Django settings
│   ├── settings.py
│   └── urls.py
├── business_scraper/            # Main app
│   ├── models.py               # Database models
│   ├── schemas.py              # Pydantic schemas
│   ├── scraper.py              # Google Maps scraper
│   ├── duckduckgo_scraper.py   # DuckDuckGo scraper
│   ├── hsctvn_scraper.py       # HSCTVN scraper
│   ├── services.py             # Business logic
│   ├── api.py                  # API endpoints
│   ├── admin.py                # Admin panel
│   └── migrations/             # Database migrations
├── manage.py
├── requirements.txt
├── docker-compose.yml
├── .env.example
└── README.md
```

## So sánh 3 Scrapers

| Tính năng | Google Maps | DuckDuckGo | HSCTVN |
|-----------|-------------|------------|--------|
| **Search by** | Keyword + location | Keyword + location | Date |
| **Phone** | ✅ 90% | ✅ 80% | ✅ 100% |
| **Email** | ✅ 30% | ✅ 50% | ❌ 0% |
| **Address** | ✅ 90% | ✅ 80% | ✅ 100% |
| **Tax ID** | ❌ 0% | ❌ 0% | ✅ 100% |
| **Legal Rep** | ❌ 0% | ❌ 0% | ✅ 100% |
| **Issue Date** | ❌ 0% | ❌ 0% | ✅ 100% |
| **Status** | ❌ 0% | ❌ 0% | ✅ 100% |
| **Rating** | ✅ Yes | ❌ No | ❌ No |
| **GPS** | ✅ Yes | ❌ No | ❌ No |
| **Speed** | Fast | Medium | Slow (detail pages) |
| **Use case** | Find businesses | Web search | Track new companies |

## Admin Panel

Truy cập Django Admin: **http://localhost:8000/admin**

Features:
- Quản lý SearchQuery và Business
- Filter theo source, status, date
- Search businesses theo name, phone, email
- Export data
- Bulk actions

## Environment Variables

File `.env` quan trọng:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/business_scraper_db

# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Scraper settings (optional)
SCRAPER_HEADLESS=True
SCRAPER_TIMEOUT=30000
```

## Troubleshooting

### 1. Playwright không hoạt động

```bash
playwright install chromium
playwright install-deps
```

### 2. PostgreSQL connection error

```bash
# Kiểm tra Docker
docker-compose ps

# Restart PostgreSQL
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### 3. Database migration issues

```bash
# Reset migrations (careful!)
python manage.py migrate business_scraper zero
python manage.py migrate

# Or create fresh database
docker-compose down -v
docker-compose up -d
python manage.py migrate
```

### 4. Scraper không tìm thấy dữ liệu

- **Google Maps**: UI thay đổi thường xuyên, check selectors
- **DuckDuckGo**: Bot detection, thử với proxy
- **HSCTVN**: HTML structure thay đổi, check regex patterns

**Debug mode:**
```python
# Trong .env
SCRAPER_HEADLESS=False
```

Chạy scraper sẽ hiển thị browser để debug.

### 5. Import errors

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check Python version
python --version  # Should be 3.12+
```

## Development

### Running tests

```bash
python manage.py test
```

### Creating new migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Django shell

```bash
python manage.py shell
```

Example shell commands:
```python
from business_scraper.models import Business, SearchQuery

# Get all searches
searches = SearchQuery.objects.all()

# Get businesses from HSCTVN
hsctvn_businesses = Business.objects.filter(
    search_query__source='hsctvn'
)

# Get businesses with phone
with_phone = Business.objects.exclude(phone__isnull=True)

# Filter by date
from datetime import date
recent = Business.objects.filter(
    issue_date__gte=date(2025, 10, 1)
)
```

## Performance Tips

### 1. Database Indexing
Models đã có indexes cho:
- `name`, `tax_id`, `phone`, `email`
- Tăng tốc độ search

### 2. Async Operations
Tất cả scrapers sử dụng `async/await` cho hiệu suất tốt nhất.

### 3. Rate Limiting
Tránh bị ban bằng cách:
```python
# Trong scraper
await asyncio.sleep(1)  # Delay giữa requests
```

### 4. Parallel Scraping
DuckDuckGo hỗ trợ scrape nhiều URLs song song:
```python
# Automatic trong scraper
```

## Legal Disclaimer

⚠️ **QUAN TRỌNG**:

1. **Google Maps**: Scraping có thể vi phạm Terms of Service của Google. Chỉ dùng cho mục đích học tập và nghiên cứu.

2. **DuckDuckGo**: Tuân thủ robots.txt và rate limiting.

3. **HSCTVN**: Dữ liệu công khai nhưng cần tuân thủ quy định về sử dụng.

**Sử dụng với trách nhiệm của bản thân!**

## Technology Stack

- **Backend**: Django 5.0.1, Django Ninja 1.1.0
- **Database**: PostgreSQL 16
- **Scraping**: Playwright 1.41.1
- **Validation**: Pydantic via Django Ninja
- **Container**: Docker & Docker Compose

## Contributing

1. Fork project
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## License

MIT License - Chỉ dành cho mục đích học tập và nghiên cứu.

## Support

Nếu có vấn đề:
1. Check [Troubleshooting](#troubleshooting) section
2. Review API docs: http://localhost:8000/api/docs
3. Check Django admin: http://localhost:8000/admin

## Author

Built with Django Ninja, Playwright, and PostgreSQL.

---

**Happy Scraping! 🚀**
