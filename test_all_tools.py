#!/usr/bin/env python3
"""
SIN-Browser-Tools Test Suite
"""
import asyncio
from sin_browser_tools.core import manager

async def main():
    print("\n" + "="*80)
    print("  SIN-Browser-Tools-Library - Test Suite")
    print("="*80)
    
    try:
        print("\n[TEST] Starting local browser...")
        await manager.start_local(headless=True)
        print("✓ Browser started")
        
        print("\n[TEST] Navigate to example.com...")
        from sin_browser_tools.tools import navigation
        result = await navigation.browser_navigate("https://example.com")
        print(f"✓ Navigated to {result['url']}")
        
        print("\n[TEST] Get accessibility snapshot...")
        from sin_browser_tools.tools import accessibility
        snapshot = await accessibility.browser_snapshot()
        print(f"✓ Found {snapshot['ref_count']} interactive elements")
        print(f"Tree preview:\n{snapshot['tree'][:200]}...")
        
        print("\n[TEST] Take screenshot...")
        from sin_browser_tools.tools import vision
        screenshot = await vision.browser_vision(full_page=False)
        print(f"✓ Screenshot taken ({len(screenshot['base64'])} base64 chars)")
        
        print("\n[TEST] Get images...")
        images = await vision.browser_get_images()
        print(f"✓ Found {images['count']} images")
        
        print("\n[TEST] Execute console command...")
        from sin_browser_tools.tools import extraction
        result = await extraction.browser_console("document.title")
        print(f"✓ Page title: {result['result']}")
        
        print("\n" + "="*80)
        print("  ✓ ALL TESTS PASSED")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await manager.cleanup()
        print("\n✓ Browser closed")

if __name__ == "__main__":
    asyncio.run(main())
