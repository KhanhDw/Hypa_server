# Luồng dữ liệu giữa các class trong app\services\facebook\product

## Tổng quan

Các class trong thư mục `app\services\facebook\product` hoạt động cùng nhau để thực hiện quá trình scraping dữ liệu từ Facebook với các tính năng chính:

- Quản lý pool trình duyệt để tái sử dụng
- Caching dữ liệu đã scrape (cả in-memory và Redis)
- Giới hạn tần suất yêu cầu
- Hỗ trợ nhiều chế độ scrape (simple, full, super)
- Tự động điều chỉnh tốc độ scraping dựa trên hiệu suất
- Phát hiện và xử lý bất thường (anomaly detection)
- Tự động mở rộng số lượng worker (auto-scaling)
- Theo dõi và ghi chép các chỉ số hiệu suất (metrics)
- Xử lý hiệu quả các batch lớn (500-2000 URLs) thông qua chia nhỏ, tăng số lượng worker và luân phiên trình duyệt

## Các class và vai trò

### 1. AsyncFacebookScraperStreaming (scraper_core.py)

- **Vai trò chính**: Class trung tâm điều phối toàn bộ quá trình scraping
- **Tương tác với**:
  - BrowserPool: để lấy và trả lại trang web
  - RedisCache: để kiểm tra và lưu dữ liệu cache
  - RateLimiter: để giới hạn tần suất yêu cầu
  - BrowserPool: để lấy route handler
  - TaskEngine: để thực hiện các tác vụ scraping
- **Cấu hình mới**: context_reuse_limit tăng lên 250, cache_ttl 600s, enable_images=False

### 2. BrowserPool (browser_pool.py)

- **Vai trò chính**: Quản lý pool trình duyệt, context và page để tái sử dụng
- **Tương tác với**:
  - AsyncFacebookScraperStreaming: cung cấp page cho việc scraping
  - Page/Context của Playwright: tạo, quản lý và reset state của các trang
  - TaskEngine: cung cấp page và context cho các tác vụ scraping
- **Cấu hình mới**: context_reuse_limit tăng lên 250 cho việc luân phiên trình duyệt hiệu quả hơn

### 3. RedisCache (redis_cache.py)

- **Vai trò chính**: Cache dữ liệu scraping sử dụng Redis
- **Tương tác với**:
  - AsyncFacebookScraperStreaming: cung cấp phương thức get/set cache
  - TaskEngine: được sử dụng trong quá trình kiểm tra và lưu cache

### 4. RateLimiter (rate_limiter.py)

- **Vai trò chính**: Giới hạn tần suất yêu cầu để tránh bị chặn
- **Tương tác với**:
  - AsyncFacebookScraperStreaming: được gọi trước mỗi yêu cầu scraping
  - TaskEngine: được áp dụng trong quá trình thực hiện scraping

### 5. FacebookScraperAPI (scraper_api.py)

- **Vai trò chính**: API wrapper để tích hợp với FastAPI
- **Tương tác với**:
  - AsyncFacebookScraperStreaming: tạo instance để thực hiện scraping
  - Job queue: quản lý các tác vụ scraping
  - TaskEngine: sử dụng để thực hiện các tác vụ scraping
- **Cấu hình mới**: Hỗ trợ tạo nhiều job nhỏ từ batch lớn (create_job hỗ trợ chunk_size), worker xử lý batch_size=25

### 6. TaskEngine (task_engine.py)

- **Vai trò chính**: Xử lý logic chính của scraping bao gồm caching, rate limiting và điều phối tác vụ
- **Tương tác với**:
  - Fetcher: để điều phối việc lấy nội dung trang
  - Extractor: để trích xuất dữ liệu từ trang
  - RedisCache: để kiểm tra và lưu dữ liệu cache
  - RateLimiter: để giới hạn tần suất yêu cầu
  - BrowserPool (thông qua Fetcher): để lấy và trả lại trang web
  - AnomalyDetector: để theo dõi các bất thường trong quá trình scraping
  - Throttler: để điều chỉnh tốc độ scraping dựa trên hiệu suất
  - Scaler: để cập nhật thông tin về độ dài hàng đợi
- **Cấu hình mới**: get_multiple_metadata_streaming hỗ trợ batch_size (mặc định 25) để xử lý hiệu quả batch lớn

### 7. Fetcher (fetcher.py)

- **Vai trò chính**: Xử lý việc điều hướng đến URL và lấy nội dung trang
- **Tương tác với**:
  - BrowserPool: để lấy page cho việc điều hướng
  - Page của Playwright: thực hiện điều hướng đến URL
  - TaskEngine: trả về kết quả điều hướng cho TaskEngine

### 8. Extractor (extractor.py)

- **Vai trò chính**: Trích xuất dữ liệu từ trang web theo chế độ (simple, full, super)
- **Tương tác với**:
  - Page của Playwright: thực hiện trích xuất dữ liệu từ trang
  - TaskEngine: trả về dữ liệu đã trích xuất cho TaskEngine
  - Metrics: ghi lại thời gian trích xuất dữ liệu

### 9. Metrics (metrics.py)

- **Vai trò chính**: Theo dõi và ghi chép các chỉ số hiệu suất của hệ thống scraping
- **Tương tác với**:
  - Tất cả các class khác: ghi lại các chỉ số như số lần scrape, thời gian điều hướng, thời gian trích xuất, v.v.

### 10. AnomalyDetector (anomaly_detector.py)

- **Vai trò chính**: Phát hiện các bất thường trong quá trình scraping như độ trễ tăng đột biến, rate limit tăng, hoặc sử dụng bộ nhớ cao
- **Tương tác với**:
  - TaskEngine: nhận thông tin về thời gian điều hướng và cập nhật phát hiện bất thường
  - Throttler: cung cấp thông tin về các bất thường để điều chỉnh tốc độ scraping
  - Scaler: cung cấp thông tin về các bất thường để ra quyết định mở rộng hoặc thu hẹp hệ thống

### 11. Throttler (throttler.py)

- **Vai trò chính**: Tự động điều chỉnh tốc độ scraping dựa trên các yếu tố như độ trễ điều hướng, tỷ lệ cache miss, sự kiện rate limit và mức sử dụng bộ nhớ
- **Tương tác với**:
  - TaskEngine: nhận thông tin về hiệu suất và điều chỉnh tốc độ scraping
  - AnomalyDetector: nhận thông tin về các bất thường để điều chỉnh tốc độ
  - Metrics: ghi lại các chỉ số liên quan đến hiệu suất
- **Cấu hình mới**: base_delay giảm còn 0.05s, max_delay giảm còn 3.0s, window sizes nhỏ hơn để phản ứng nhanh hơn

### 12. Scaler (scaler.py)

- **Vai trò chính**: Tự động mở rộng số lượng worker dựa trên độ dài hàng đợi và thời gian chờ trong hàng đợi
- **Tương tác với**:
  - TaskEngine: nhận thông tin về độ dài hàng đợi và thời gian chờ để đưa ra quyết định mở rộng
  - AnomalyDetector: sử dụng thông tin về bất thường để ra quyết định về việc khởi động lại worker
- **Cấu hình mới**: min_workers tăng lên 4, queue_length_scale_up giảm xuống 5, cooldown_period giảm xuống 20s

### 13. LargeBatchProcessor (large_batch_processor.py)

- **Vai trò chính**: Xử lý hiệu quả các batch lớn (500-2000 URLs) bằng cách chia nhỏ, quản lý worker và theo dõi tiến độ
- **Tương tác với**:
  - FacebookScraperAPI: để tạo và theo dõi các job nhỏ
  - TaskEngine: để thực hiện các tác vụ scraping trong từng chunk
- **Tính năng**: Tự động cấu hình worker, chia nhỏ batch, theo dõi tiến độ và tổng hợp kết quả

## Luồng dữ liệu chính

### Quá trình scraping đơn lẻ

1. `TaskEngine.get_facebook_metadata(url)`
   - Kiểm tra cache cục bộ (SharedInMemoryCache) → nếu có dữ liệu, trả về ngay
   - Kiểm tra cache Redis → nếu có dữ liệu, trả về và lưu vào cache cục bộ
   - Gọi `Throttler.get_current_delay()` để áp dụng độ trễ nếu cần
   - Gọi `RateLimiter.acquire()` để giới hạn tần suất
   - Gọi `BrowserPool.get_page()` để lấy trang và context
   - Gọi `Fetcher.fetch_page_content()` để điều hướng đến URL
   - Ghi lại thời gian điều hướng cho `Throttler` và `AnomalyDetector`
   - Gọi `Extractor.extract_data()` để trích xuất dữ liệu theo chế độ (simple, full, super)
   - Ghi lại thời gian trích xuất cho Metrics
   - Lưu kết quả vào cache cục bộ và Redis
   - Gọi `BrowserPool.return_page()` để trả trang và context về pool
   - Gọi `RateLimiter.release()` để kết thúc giới hạn tần suất
   - Cập nhật các chỉ số hiệu suất trong Metrics

### Quá trình scraping nhiều URL (batch lớn)

1. `LargeBatchProcessor.process_large_batch(urls)`
   - Chia URLs thành các chunk nhỏ (mặc định 25 URLs/chunk)
   - Tạo nhiều job nhỏ từ batch lớn thông qua `FacebookScraperAPI.create_job()`
   - Khởi động nhiều worker (mặc định 8) để xử lý song song các chunk
   - Theo dõi tiến độ của từng job và tổng hợp kết quả

2. `TaskEngine.get_multiple_metadata_streaming(urls, batch_size=25)`
   - Xử lý URLs theo batch nhỏ (25 URLs mỗi batch) để quản lý tài nguyên hiệu quả
   - Sử dụng `ModeBasedQueueManager` để quản lý hàng đợi theo chế độ
   - Ghi lại thời gian chờ trong hàng đợi cho Metrics
   - Gọi `get_facebook_metadata()` cho từng URL
   - Trả về kết quả theo thứ tự hoàn thành (async generator)
   - Cập nhật độ dài hàng đợi cho Scaler trong quá trình xử lý

### Quá trình quản lý trình duyệt

1. `BrowserPool.initialize()`

   - Tạo Playwright instance
   - Tạo trình duyệt và các trang, đưa vào queue
   - Đăng ký route handler để chặn tài nguyên không cần thiết

2. `BrowserPool.get_page()`

   - Lấy page từ queue
   - Tạo thêm page nếu queue rỗng

3. `BrowserPool.return_page(page)`
   - Reset state của page (navigates to about:blank)
   - Trả page về queue để tái sử dụng
   - Context được tái sử dụng đến 250 lần trước khi reset (giúp luân phiên trình duyệt hiệu quả)

### Quá trình tự điều chỉnh hiệu suất

1. `Throttler.update_navigation_time(duration, mode)`

   - Cập nhật thời gian điều hướng vào lịch sử (cửa sổ nhỏ hơn 15 để phản ứng nhanh)
   - Gửi thông tin đến `AnomalyDetector` để phát hiện bất thường
   - Điều chỉnh độ trễ nếu thời gian điều hướng vượt ngưỡng

2. `Throttler.update_cache_stats(cache_hit)`

   - Cập nhật trạng thái cache hit/miss (cửa sổ nhỏ hơn để phản ứng nhanh)
   - Điều chỉnh độ trễ nếu tỷ lệ cache miss vượt ngưỡng

3. `Throttler.record_rate_limit_event()`

   - Ghi nhận sự kiện rate limit
   - Gửi thông tin đến `AnomalyDetector`
   - Áp dụng throttling mạnh hơn nếu có sự kiện rate limit

### Quá trình phát hiện bất thường

1. `AnomalyDetector.add_navigation_time(duration, mode)`

   - Sử dụng Z-score và EWMA để phát hiện bất thường về độ trễ
   - Ghi lại sự kiện bất thường

2. `AnomalyDetector.add_rate_limit_event()`

   - Ghi nhận sự kiện rate limit
   - Phát hiện các bất thường về tần suất rate limit

3. `AnomalyDetector.add_memory_usage(memory_mb, browser_id)`

   - Ghi nhận mức sử dụng bộ nhớ
   - Phát hiện các bất thường về sử dụng bộ nhớ

### Quá trình tự động mở rộng

1. `Scaler.add_queue_wait_time(wait_time, mode)`

   - Ghi nhận thời gian chờ trong hàng đợi theo chế độ
   - Tính toán P90 của thời gian chờ để đưa ra quyết định mở rộng

2. `Scaler.update_queue_length(length, mode)`

   - Cập nhật độ dài hàng đợi theo chế độ
   - Ghi nhận thông tin để đưa ra quyết định mở rộng

3. `Scaler.scale_up()` hoặc `Scaler.scale_down()`

   - Tăng hoặc giảm số lượng worker dựa trên các tiêu chí đã định nghĩa:
     - Mở rộng nhanh hơn khi hàng đợi > 5 mục
     - Thu hẹp khi hàng đợi < 2 mục
     - Phản ứng nhanh hơn với thời gian cooldown 20s

### Quá trình quản lý API

1. `FacebookScraperAPI.start_worker()`

   - Tạo các worker task (mặc định 8 worker)
   - Mỗi worker quản lý một instance `AsyncFacebookScraperStreaming`

2. `FacebookScraperAPI.create_job(urls, chunk_size=25)`
   - Chia URLs thành các chunk nhỏ (25 URLs mỗi chunk)
   - Tạo nhiều job ID duy nhất cho các chunk
   - Đưa các job vào queue để được xử lý bởi các worker
   - Worker sẽ gọi `TaskEngine.get_multiple_metadata_streaming()` với batch_size=25

## Tính năng chính của luồng dữ liệu

1. **Tái sử dụng tài nguyên**: BrowserPool giúp tái sử dụng trình duyệt và trang, giảm overhead
2. **Caching đa lớp**: Cả cache cục bộ và Redis giúp tăng tốc độ xử lý
3. **Giới hạn tần suất**: RateLimiter ngăn chặn việc bị chặn do gửi quá nhiều request
4. **Xử lý lỗi**: Các lớp xử lý lỗi riêng biệt và có cơ chế fallback
5. **Hỗ trợ nhiều chế độ**: 3 chế độ trích xuất dữ liệu (simple, full, super)
6. **Queue-based processing**: FacebookScraperAPI hỗ trợ xử lý tác vụ nền
7. **Tự điều chỉnh hiệu suất**: Throttler tự động điều chỉnh tốc độ scraping dựa trên hiệu suất thực tế
8. **Phát hiện bất thường**: AnomalyDetector phát hiện các hiện tượng bất thường trong quá trình scraping
9. **Tự động mở rộng**: Scaler tự động điều chỉnh số lượng worker dựa trên tải hệ thống
10. **Theo dõi hiệu suất**: Metrics theo dõi toàn bộ chỉ số hiệu suất của hệ thống
11. **Queue theo chế độ**: Quản lý hàng đợi riêng biệt cho từng chế độ scraping (simple, full, super)
12. **Xử lý batch lớn hiệu quả**: Hỗ trợ xử lý 500-2000 URLs qua cơ chế chia nhỏ, tăng worker, luân phiên trình duyệt
13. **Tối ưu cho batch lớn**: 
    - Worker nhẹ: 5 context × 5 page = 25 pages mỗi worker
    - Tăng số worker: 4-10 worker để xử lý song song
    - Chia nhỏ batch: 20-50 URLs mỗi chunk để tránh quá tải
    - Luân phiên trình duyệt: Context reset mỗi 250 navigation để tránh memory leak
    - Throttling thích ứng: Điều chỉnh độ trễ khi navigation tăng
