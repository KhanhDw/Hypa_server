# Kino Server - Project Documentation

## Overview

Kino Server is a FastAPI-based web server designed to extract and serve metadata from URLs. The primary function of this server is to provide comprehensive metadata for a given URL, which is commonly used for link preview functionality in web applications (e.g., when sharing links on social media platforms). The server follows SOLID principles with a service-oriented architecture and includes caching for performance optimization.

## Project Architecture

The project follows a clean architecture pattern with the following main components:

- **app/main.py**: The main FastAPI application with CORS configuration and API endpoints
- **app/services/**: Contains all service classes following dependency injection principles
- **app/core/models.py**: Defines the Metadata dataclass structure
- **app/core/**: Core functionality and models

### Service Layer Architecture

The service layer implements dependency injection with a container pattern:

- **ServiceContainer**: Manages all service dependencies
- **URLValidator**: Validates and sanitizes incoming URLs
- **WebFetcher**: Fetches HTML content from URLs
- **PlatformDetector**: Detects the platform (e.g., YouTube, Facebook, Twitter) of a URL
- **MetadataExtractor**: Extracts comprehensive metadata from HTML using Open Graph and Twitter Card protocols
- **CacheService**: Implements caching to improve performance for frequently requested URLs
- **MetadataService**: Orchestrates the metadata extraction process

### Core Models

- **Metadata**: Dataclass containing comprehensive metadata fields including:
  - Open Graph properties (title, description, image, site_name, etc.)
  - Twitter Card properties (twitter_card, twitter_site, etc.)
  - Article properties (author, published_time, etc.)
  - Additional properties (keywords, favicon, language, etc.)

## API Endpoints

### GET /
- **Description**: Health check endpoint
- **Response**: `{"message": "Simple Server is running!"}`

### GET /metadata
- **Description**: Extracts metadata from the provided URL
- **Query Parameters**: `url` (required) - The URL to extract metadata from
- **Response**: JSON object containing comprehensive metadata fields
- **Example**: `http://127.0.0.1:8000/metadata?url=https://www.example.com`

### GET /docs
- **Description**: Swagger UI documentation for the API

## Technology Stack

- **Framework**: FastAPI (0.115.4)
- **ASGI Server**: Uvicorn (0.32.0)
- **HTTP Client**: HTTPX (0.28.1)
- **HTML Parsing**: BeautifulSoup4 (4.14.3) and lxml (6.0.2)
- **Environment Management**: python-dotenv (1.0.1)
- **Validation**: Pydantic (2.9.2)
- **Testing**: Pytest (9.0.1) and TestClient
- **Caching**: In-memory caching implemented with cachetools (6.2.2)

## Dependencies

The project includes comprehensive dependencies for:

- **Web Framework**: FastAPI and Uvicorn
- **Data Validation**: Pydantic and Pydantic Settings
- **Database Connectivity**: SQLAlchemy and asyncpg (PostgreSQL)
- **Task Queuing**: Celery and Redis
- **Security**: bcrypt, passlib, python-jose for authentication and password hashing
- **Templating**: Jinja2
- **Testing**: pytest and pytest-asyncio

## Setup and Running

### Local Development

1. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python -m uvicorn app.main:app --reload
   ```
   
   Or use the start script:
   ```bash
   start.bat
   ```

### Production Deployment

For production, remove the `--reload` flag and adjust the host and port as needed:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Testing

The project includes comprehensive tests in `test_app.py` that verify:

- Basic endpoint functionality
- Metadata extraction for various URLs
- Error handling for invalid URLs
- Response structure validation
- Cache functionality verification

To run tests:
```bash
pytest
```

Or run the test file directly:
```bash
python test_app.py
```

## Configuration

### CORS Settings

The application is configured with CORS middleware to allow cross-origin requests. Currently set to allow all origins (`"*"`), which should be restricted in production environments.

### Environment Variables

The project uses python-dotenv for environment variable management. Commonly used variables may include:
- Database connection strings
- API keys
- Cache configuration
- Server host and port settings

## Development Guidelines

### Commit Convention

The project follows conventional commits with these types:
- `feat`: New features
- `fix`: Bug fixes
- `refactor`: Code improvements without functional changes
- `docs`: Documentation updates
- `style`: Code formatting changes
- `test`: Test-related changes
- `chore`: General maintenance
- `perf`: Performance improvements
- `revert`: Reverting previous commits

### File Structure Conventions

- Place all API endpoints in `app/main.py`
- Implement business logic in the service layer (`app/services/`)
- Define data models in `app/core/models.py`
- Add utility functions to `app/utils/` (if created)
- Place tests in the root directory or in a dedicated `tests/` directory

## Common Use Cases

This server is particularly useful for:
- Link preview functionality in chat/messaging applications
- Social media sharing with rich preview cards
- Content aggregation services
- Any application requiring URL metadata extraction

## Performance Considerations

- The service implements caching to reduce repeated requests to external sources
- Asynchronous operations are used where possible for better performance
- HTML parsing is optimized with lxml backend when available

## Security Considerations

- URL validation is performed to prevent requests to internal resources
- Input validation is implemented for all API endpoints
- Cross-origin requests are configured (currently allowing all origins - adjust for production)

## Troubleshooting

Common issues and solutions:
1. **URL validation errors**: Ensure URLs are properly formatted and accessible
2. **Metadata extraction failures**: Some websites may block automated access or not have proper metadata
3. **Performance issues**: Check cache effectiveness and consider adding additional caching layers
4. **Dependency conflicts**: Use virtual environments to manage project dependencies

## Recent Improvements to Service Layer

The service layer has been improved with the following clean code practices:

### 1. Interface Design
- All services now have well-defined interfaces following the Dependency Inversion Principle
- Type hints properly use interfaces instead of concrete implementations

### 2. Exception Handling
- Custom exception hierarchy created for better error management
- All services now use the new exception types for more specific error handling

### 3. Logging
- Comprehensive logging added throughout all service layers
- Different log levels (info, debug, warning, error) used appropriately
- All operations are now properly logged for debugging and monitoring

### 4. Code Organization
- Large services were split into smaller, more focused components
- MetadataExtractor was separated into specialized utility classes (HTMLParser, metadata extractors)
- Single Responsibility Principle is now better followed

### 5. Documentation and Type Hints
- Detailed docstrings added to all public methods and classes
- Type hints improved throughout the service layer
- Better parameter and return value documentation

### 6. Dependency Injection
- ServiceContainer optimized to follow best practices
- Proper dependency management and lifecycle handling
- Interface-based service retrieval implemented