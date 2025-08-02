#!/usr/bin/env python3
"""
Test the ComicVineService get_volume_issues method
"""

import os
import sys

# Add the project path so we can import our modules
sys.path.insert(0, '/Users/rkuykendall/Library/CloudStorage/Dropbox/Code/weeklypulls2/weeklypulls')

# Mock Django settings for the service
class MockSettings:
    COMICVINE_API_KEY = os.getenv('COMICVINE_API_KEY')
    COMICVINE_CACHE_EXPIRE_HOURS = 24 * 6

sys.modules['django.conf'] = type('MockDjango', (), {'settings': MockSettings})()

from weeklypulls.apps.comicvine.services import ComicVineService


def test_service():
    """Test the ComicVineService get_volume_issues method"""
    
    api_key = os.getenv('COMICVINE_API_KEY')
    if not api_key:
        print("ERROR: Please set COMICVINE_API_KEY environment variable")
        return False
    
    print("Testing ComicVineService.get_volume_issues()...")
    
    service = ComicVineService()
    
    # Test with volume 144026, get first 3 issues
    volume_id = 144026
    limit = 3
    
    issues = service.get_volume_issues(volume_id, limit=limit)
    
    if not issues:
        print("ERROR: No issues returned")
        return False
    
    print(f"SUCCESS: Found {len(issues)} issues")
    
    for i, issue in enumerate(issues):
        print(f"  Issue {i+1}: ID={issue['id']}, Number={issue['number']}, Name={issue['name']}")
    
    # Test the issue ID extraction that would be used in the conversion
    issue_ids = [issue['id'] for issue in issues]
    print(f"\nIssue IDs for conversion: {issue_ids}")
    
    return True


if __name__ == "__main__":
    success = test_service()
    sys.exit(0 if success else 1)
