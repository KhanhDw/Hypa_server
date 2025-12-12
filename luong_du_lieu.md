# Luồng dữ liệu giữa các class trong app\services\facebook\product

## Tổng quan

Các class trong thư mục `app\services\facebook\product` hoạt động cùng nhau để thực hiện quá trình scraping dữ liệu từ Facebook với các tính năng chính:

- Quản lý pool trình duyệt để tái sử dụng
- Caching dữ liệu đã scrape
- Giới hạn tần suất yêu cầu
- Hỗ trợ nhiều chế độ scrape (simple, full, super)

## Các class và vai trò

### 1. AsyncFacebookScraperStreaming (scraper_core.py)

- **Vai trò chính**: Class trung tâm điều phối toàn bộ quá trình scraping
- **Tương tác với**:
  - BrowserPool: để lấy và trả lại trang web
  - RedisCache: để kiểm tra và lưu dữ liệu cache
  - RateLimiter: để giới hạn tần suất yêu cầu
  - BrowserPool: để lấy route handler

### 2. BrowserPool (browser_pool.py)

- **Vai trò chính**: Quản lý pool trình duyệt, context và page để tái sử dụng
- **Tương tác với**:
  - AsyncFacebookScraperStreaming: cung cấp page cho việc scraping
  - Page/Context của Playwright: tạo, quản lý và reset state của các trang

### 3. RedisCache (redis_cache.py)

- **Vai trò chính**: Cache dữ liệu scraping sử dụng Redis
- **Tương tác với**:
  - AsyncFacebookScraperStreaming: cung cấp phương thức get/set cache

### 4. RateLimiter (rate_limiter.py)

- **Vai trò chính**: Giới hạn tần suất yêu cầu để tránh bị chặn
- **Tương tác với**:
  - AsyncFacebookScraperStreaming: được gọi trước mỗi yêu cầu scraping

### 5. FacebookScraperAPI (scraper_api.py)

- **Vai trò chính**: API wrapper để tích hợp với FastAPI
- **Tương tác với**:
  - AsyncFacebookScraperStreaming: tạo instance để thực hiện scraping
  - Job queue: quản lý các tác vụ scraping

## Luồng dữ liệu chính

### Quá trình scraping đơn lẻ

1. `AsyncFacebookScraperStreaming.get_facebook_metadata(url)`
   - Kiểm tra cache cục bộ → nếu có dữ liệu cũ, trả về ngay
   - Kiểm tra cache Redis → nếu có dữ liệu, trả về và lưu vào cache cục bộ
   - Gọi `RateLimiter.acquire()` để giới hạn tần suất
   - Nếu dùng browser pool: gọi `BrowserPool.get_page()` để lấy trang
   - Thực hiện scraping trên trang (gồm navigate, đợi, trích xuất dữ liệu)
   - Áp dụng chế độ trích xuất (simple, full, super) theo cấu hình
   - Lưu kết quả vào cache cục bộ và Redis
   - Gọi `BrowserPool.return_page()` để trả trang về pool
   - Gọi `RateLimiter.release()` để kết thúc giới hạn tần suất

### Quá trình scraping nhiều URL

1. `AsyncFacebookScraperStreaming.get_multiple_metadata_streaming(urls)`
   - Gọi `get_facebook_metadata()` cho từng URL
   - Trả về kết quả theo thứ tự hoàn thành (async generator)

### Quá trình quản lý trình duyệt

1. `BrowserPool.initialize()`

   - Tạo Playwright instance
   - Tạo trình duyệt và các trang, đưa vào queue
   - Đăng ký route handler để chặn tài nguyên không cần thiết

2. `BrowserPool.get_page()`

   - Lấy page từ queue
   - Tạo thêm page nếu queue rỗng

3. `BrowserPool.return_page(page)`
   - Reset state của page (xóa cookies, storage)
   - Trả page về queue để tái sử dụng

### Quá trình quản lý API

1. `FacebookScraperAPI.start_worker()`

   - Tạo các worker task
   - Mỗi worker quản lý một instance `AsyncFacebookScraperStreaming`

2. `FacebookScraperAPI.create_job(urls)`
   - Tạo job ID duy nhất
   - Đưa job vào queue để được xử lý bởi worker
   - Worker sẽ gọi `AsyncFacebookScraperStreaming.get_multiple_metadata_streaming()`

## Tính năng chính của luồng dữ liệu

1. **Tái sử dụng tài nguyên**: BrowserPool giúp tái sử dụng trình duyệt và trang, giảm overhead
2. **Caching đa lớp**: Cả cache cục bộ và Redis giúp tăng tốc độ xử lý
3. **Giới hạn tần suất**: RateLimiter ngăn chặn việc bị chặn do gửi quá nhiều request
4. **Xử lý lỗi**: Các lớp xử lý lỗi riêng biệt và có cơ chế fallback
5. **Hỗ trợ nhiều chế độ**: 3 chế độ trích xuất dữ liệu (simple, full, super)
6. **Queue-based processing**: FacebookScraperAPI hỗ trợ xử lý tác vụ nền
