#!/usr/bin/env python3
"""
Standalone test script for ComicVine API issue fetching
without Django database dependencies
"""

import os
import sys
import time

# Add the project path so we can import our modules
sys.path.insert(0, '/Users/rkuykendall/Library/CloudStorage/Dropbox/Code/weeklypulls2/weeklypulls')

from simyan.comicvine import Comicvine
from simyan.sqlite_cache import SQLiteCache
from simyan.exceptions import ServiceError


def test_comicvine_issues():
    """Test fetching issues for a specific volume"""
    
    # You'll need to set your ComicVine API key
    api_key = os.getenv('COMICVINE_API_KEY')
    if not api_key:
        print("ERROR: Please set COMICVINE_API_KEY environment variable")
        return False
    
    print(f"Testing ComicVine API with volume 144026...")
    
    try:
        # Initialize Simyan
        cache = SQLiteCache()
        cv = Comicvine(api_key=api_key, cache=cache)
        
        # Test fetching issues for volume 144026
        volume_id = 144026
        limit = 5  # Just get first 5 issues for testing
        
        print(f"Fetching first {limit} issues for volume {volume_id}...")
        start_time = time.time()
        
        # Get issues for the volume
        issues = cv.list_issues(
            params={
                'filter': f'volume:{volume_id}',
                'sort': 'issue_number:asc'
            },
            max_results=limit
        )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        print(f"API SUCCESS: Found {len(issues)} issues in {response_time_ms}ms")
        
        # Display the issues
        for i, issue in enumerate(issues):
            print(f"  Issue {i+1}: ID={issue.id}")
            print(f"    Available attributes: {dir(issue)}")
            # Print a few key attributes
            print(f"    Name: {getattr(issue, 'name', 'N/A')}")
            print(f"    Date Added: {getattr(issue, 'date_added', 'N/A')}")
            if hasattr(issue, 'issue_number'):
                print(f"    Issue Number: {issue.issue_number}")
            elif hasattr(issue, 'number'):
                print(f"    Number: {issue.number}")
        
        # Test the conversion logic
        issue_ids = [issue.id for issue in issues]
        print(f"\nIssue IDs that would be used: {issue_ids}")
        
        return True
        
    except ServiceError as e:
        print(f"API ERROR: Simyan error: {str(e)}")
        return False
        
    except Exception as e:
        print(f"API ERROR: Unexpected error: {str(e)}")
        return False


if __name__ == "__main__":
    success = test_comicvine_issues()
    sys.exit(0 if success else 1)
