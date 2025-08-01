#!/usr/bin/env python3
"""
Standalone ComicVine API test without Django database dependency
"""
import os
from simyan.comicvine import Comicvine
from simyan.sqlite_cache import SQLiteCache
from simyan.exceptions import ServiceError

def test_comicvine_api():
    # Get API key from environment
    api_key = os.environ.get('COMICVINE_API_KEY')
    
    if not api_key:
        print("❌ COMICVINE_API_KEY environment variable not set!")
        print("Set it with: export COMICVINE_API_KEY='your_api_key_here'")
        return False
    
    print(f"✅ API Key found (ending in: ...{api_key[-4:]})")
    
    # Initialize Simyan
    try:
        cache = SQLiteCache()
        cv = Comicvine(api_key=api_key, cache=cache)
        print("✅ Simyan initialized with SQLite caching")
    except Exception as e:
        print(f"❌ Failed to initialize Simyan: {e}")
        return False
    
    # Test with a known volume ID
    test_volume_id = 100709  # Amazing Spider-Man (2018)
    
    print(f"\n🕷️  Testing with volume ID {test_volume_id} (Amazing Spider-Man 2018)...")
    
    try:
        volume = cv.get_volume(test_volume_id)
        
        if volume:
            print("✅ API call successful!")
            print(f"   Name: {volume.name}")
            print(f"   Start Year: {volume.start_year}")
            print(f"   Issue Count: {volume.issue_count}")
            print(f"   Publisher: {volume.publisher.name if volume.publisher else 'N/A'}")
            print(f"   ComicVine URL: {volume.site_url}")
            return True
        else:
            print("❌ API call returned None")
            return False
            
    except ServiceError as e:
        print(f"❌ Simyan/ComicVine error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("🦸 ComicVine API Standalone Test")
    print("=" * 40)
    
    success = test_comicvine_api()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 Test completed successfully!")
        print("Your ComicVine integration is working!")
    else:
        print("💥 Test failed!")
        print("Check your API key and internet connection.")
