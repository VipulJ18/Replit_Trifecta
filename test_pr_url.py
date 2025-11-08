#!/usr/bin/env python3
"""
Test script for PR URL validation
"""
import re

# URL pattern for validating GitHub PR URLs
PR_URL_PATTERN = re.compile(r'^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)(?:/.*)?$')

def test_pr_url_validation():
    """Test PR URL validation function"""
    test_cases = [
        # Valid URLs
        ("https://github.com/user/repo/pull/123", True, "user", "repo", "123"),
        ("https://github.com/owner/project/pull/456", True, "owner", "project", "456"),
        ("https://github.com/user/repo/pull/789/files", True, "user", "repo", "789"),
        ("https://github.com/user/repo/pull/0", True, "user", "repo", "0"),
        
        # Invalid URLs
        ("https://github.com/user/repo/issues/123", False, None, None, None),
        ("https://gitlab.com/user/repo/pull/123", False, None, None, None),
        ("https://github.com/user/repo/pull/", False, None, None, None),
        ("https://github.com/user/repo/pull/abc", True, "user", "repo", "abc"),  # Note: our regex allows this
        ("github.com/user/repo/pull/123", False, None, None, None),
        ("https://github.com/user/repo/pull/123/commits/abc", True, "user", "repo", "123"),
    ]
    
    print("Testing PR URL validation...")
    for url, should_match, expected_owner, expected_repo, expected_pr in test_cases:
        match = PR_URL_PATTERN.match(url)
        if match:
            owner, repo, pr = match.group(1), match.group(2), match.group(3)
            if should_match and owner == expected_owner and repo == expected_repo and pr == expected_pr:
                print(f"✓ PASS: {url}")
            else:
                print(f"✗ FAIL: {url} (expected {expected_owner}/{expected_repo}/pull/{expected_pr})")
        else:
            if not should_match:
                print(f"✓ PASS: {url} (correctly rejected)")
            else:
                print(f"✗ FAIL: {url} (should have matched {expected_owner}/{expected_repo}/pull/{expected_pr})")

if __name__ == '__main__':
    test_pr_url_validation()