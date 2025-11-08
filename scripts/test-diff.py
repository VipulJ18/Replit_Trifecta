#!/usr/bin/env python3
"""
Test script to validate PR diff fetching functionality
"""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from main import fetch_pr_diff, fetch_pr_diff_fallback

def main():
    # Get test PR URL from environment
    test_pr_url = os.environ.get('TEST_PR_URL')
    if not test_pr_url:
        print("Error: TEST_PR_URL environment variable not set")
        print("Usage: TEST_PR_URL=https://github.com/owner/repo/pull/number python test-diff.py")
        sys.exit(1)
    
    # Parse the URL (simple parsing for test)
    # Expected format: https://github.com/owner/repo/pull/number
    parts = test_pr_url.split('/')
    if len(parts) < 7 or parts[2] != 'github.com' or parts[5] != 'pull':
        print(f"Error: Invalid GitHub PR URL format: {test_pr_url}")
        sys.exit(1)
    
    owner = parts[3]
    repo = parts[4]
    pr_number = parts[6]
    
    print(f"Testing diff fetch for PR #{pr_number} in {owner}/{repo}")
    
    # Try fetching with primary method
    print("Attempting to fetch diff using GitHub API...")
    diff_content = fetch_pr_diff(owner, repo, pr_number)
    
    if not diff_content:
        print("Primary method failed, trying fallback...")
        diff_content = fetch_pr_diff_fallback(owner, repo, pr_number)
    
    if not diff_content:
        print("Error: Failed to fetch diff content with both methods")
        sys.exit(1)
    
    # Print first 40 lines of diff
    print("\nFirst 40 lines of diff:")
    print("=" * 50)
    lines = diff_content.split('\n')
    for i, line in enumerate(lines[:40]):
        print(f"{i+1:2d}: {line}")
    
    # Check if it looks like a valid diff
    if any(line.startswith('diff --git') for line in lines[:10]):
        print("\n✓ Success: Found valid diff content")
    else:
        print("\n⚠ Warning: Content doesn't appear to be a standard git diff")
    
    print(f"\nTotal lines in diff: {len(lines)}")
    print("✓ Test completed successfully")

if __name__ == '__main__':
    main()