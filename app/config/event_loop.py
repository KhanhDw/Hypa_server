# config/event_loop.py
import sys
import asyncio


def setup_event_loop():
    """Thiết lập event loop đúng cho Playwright trên Windows"""
    if sys.platform == 'win32':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            print("WindowsSelectorEventLoopPolicy set successfully")
        except Exception as e:
            print(f"Failed to set WindowsSelectorEventLoopPolicy: {e}")
    else:
        print(f"Platform {sys.platform} - using default event loop")
