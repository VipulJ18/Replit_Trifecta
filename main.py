import os
import json
import re
import time
import requests
import traceback
import google.generativeai as genai
from dotenv import load_dotenv

    # Load environment variables from .env file
    load_dotenv()

    from flask import Flask, request, jsonify, send_from_directory
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    app = Flask(__name__, static_folder='static')

    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

    # Configure Gemini
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
    else:
        model = None

    slack_client = WebClient(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None

    CHANNEL_MAPPING = {
        'CRITICAL': '#dev-urgent',
        'NEEDS_REVIEW': '#dev-main',
        'GOOD': '#dev-feed'
    }

    # URL pattern for validating GitHub PR URLs
    PR_URL_PATTERN = re.compile(r'^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)(?:/.*)?$')

    @app.route('/api/github-webhook', methods=['POST'])
    def github_webhook():
        try:
            payload = request.json
            
            if not payload:
                return jsonify({"status": "error", "message": "No payload"}), 200
            
            event_type = request.headers.get('X-GitHub-Event')
            
            if event_type != 'pull_request':
                return jsonify({"status": "ignored", "reason": "Not a pull_request event"}), 200
            
            action = payload.get('action')
            if action != 'opened':
                return jsonify({"status": "ignored", "reason": f"Action is {action}, not opened"}), 200
            
            pull_request = payload.get('pull_request', {})
            diff_url = pull_request.get('diff_url')
            html_url = pull_request.get('html_url')
            
            if not diff_url or not html_url:
                print("Error: Missing diff_url or html_url in payload")
                return jsonify({"status": "error", "message": "Missing required URLs"}), 200
            
            print(f"Processing PR: {html_url}")
            
            diff_content = fetch_diff(diff_url)
            if not diff_content:
                print("Error: Failed to fetch diff content")
                return jsonify({"status": "error", "message": "Failed to fetch diff"}), 200
            
            ai_result = analyze_with_ai(diff_content)
            if not ai_result:
                print("Error: Failed to analyze with AI")
                return jsonify({"status": "error", "message": "AI analysis failed"}), 200
            
            verdict = ai_result.get('verdict')
            comment = ai_result.get('comment')
            
            print(f"AI Verdict: {verdict} - {comment}")
            
            slack_success = send_to_slack(verdict, comment, html_url)
            if not slack_success:
                print(f"WARNING: Slack notification failed for PR {html_url} (verdict: {verdict})")
            
            return jsonify({"status": "success", "verdict": verdict}), 200
            
        except Exception as e:
            print(f"Error in webhook handler: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 200


    def validate_pr_url(pr_url):
        """Validate GitHub PR URL and extract owner, repo, and PR number"""
        match = PR_URL_PATTERN.match(pr_url)
        if not match:
            return None, None, None
        return match.group(1), match.group(2), match.group(3)


    def fetch_pr_diff(owner, repo, pr_number):
        """Fetch PR diff using GitHub API with proper headers and authentication"""
        # Try primary endpoint first
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {
            "Accept": "application/vnd.github.v3.diff",
            "User-Agent": "GitHub-PR-Triaging-Agent"
        }
        
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        
        # Retry logic for rate limiting and transient errors
        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=10)
                
                # Handle rate limiting
                if response.status_code == 429:
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    current_time = int(time.time())
                    wait_time = min(reset_time - current_time + 1, 60)  # Max 60 seconds
                    if wait_time > 0:
                        time.sleep(wait_time)
                    continue
                
                # Handle other server errors
                if response.status_code >= 500:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
                response.raise_for_status()
                return response.text
                
            except requests.exceptions.RequestException as e:
                if attempt == 2:  # Last attempt
                    raise e
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return None


    def fetch_pr_diff_fallback(owner, repo, pr_number):
        """Fallback method to fetch PR diff"""
        url = f"https://patch-diff.githubusercontent.com/raw/{owner}/{repo}/pull/{pr_number}.diff"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Fallback diff fetch failed: {str(e)}")
            return None


    def fetch_diff(diff_url):
        """Original diff fetching function for webhook compatibility"""
        try:
            headers = {}
            if GITHUB_TOKEN:
                headers['Authorization'] = f'token {GITHUB_TOKEN}'
            
            response = requests.get(diff_url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching diff: {str(e)}")
            return None


    def analyze_with_ai(diff_content):
        try:
            if not model:
                print("Warning: Gemini model not initialized")
                return {"verdict": "NEEDS_REVIEW", "comment": "AI analysis unavailable - manual review required"}
            
            prompt = (
                "You are a senior software engineer acting as a code reviewer. "
                "Analyze the provided code diff and answer: What is the issue here? "
                "Respond in natural human language with a brief, clear explanation."
            )
            
            response = model.generate_content([prompt, f"Code diff:\n\n{diff_content[:4000]}"])
            
            result_text = response.text if response.text else "No response from AI"
            
            # Since we're getting natural language, we need to determine the verdict
            # We'll do this by asking the AI to classify the severity
            classification_prompt = (
                "Based on the issue description, classify the severity as either 'CRITICAL', 'NEEDS_REVIEW', or 'GOOD'. "
                "Respond with only one word: CRITICAL, NEEDS_REVIEW, or GOOD."
            )
            
            classification_response = model.generate_content([classification_prompt, result_text])
            verdict = classification_response.text.strip().upper() if classification_response.text else "NEEDS_REVIEW"
            
            if verdict not in ['CRITICAL', 'NEEDS_REVIEW', 'GOOD']:
                verdict = 'NEEDS_REVIEW'  # Default fallback
                
            return {"verdict": verdict, "comment": result_text}
            
        except Exception as e:
            print(f"Error in AI analysis: {str(e)}")
            return {"verdict": "NEEDS_REVIEW", "comment": f"AI analysis error: {str(e)} - manual review required"}


    def send_to_slack(verdict, comment, pr_url):
        try:
            if not slack_client:
                print("Warning: Slack client not initialized")
                return False
            
            channel = CHANNEL_MAPPING.get(verdict, '#dev-main')
            
            if verdict == 'CRITICAL':
                message = f"🚨 CRITICAL PR: <!here> AI found a critical issue. {comment} {pr_url}"
            elif verdict == 'NEEDS_REVIEW':
                message = f"👀 Review Needed: {comment} {pr_url}"
            else:
                message = f"✅ PR Approved: AI review passed. {comment} {pr_url}"
            
            response = slack_client.chat_postMessage(
                channel=channel,
                text=message
            )
            
            print(f"Slack message sent to #{channel}: {response['ts']}")
            return True
            
        except SlackApiError as e:
            print(f"Slack API error: {e.response['error']}")
            return False
        except Exception as e:
            print(f"Error sending to Slack: {str(e)}")
            return False


    @app.route('/api/analyze-pr', methods=['POST'])
    def analyze_pr_endpoint():
        """New endpoint for analyzing PRs directly from the UI"""
        try:
            data = request.json
            if not data:
                return jsonify({"ok": False, "code": "INVALID_JSON", "message": "Invalid JSON payload"}), 400
                
            pr_url = data.get('pr_url')
            
            if not pr_url:
                return jsonify({"ok": False, "code": "MISSING_URL", "message": "PR URL is required"}), 400
            
            # Validate PR URL
            owner, repo, pr_number = validate_pr_url(pr_url)
            if not owner or not repo or not pr_number:
                return jsonify({"ok": False, "code": "INVALID_URL", "message": "Invalid GitHub PR URL format"}), 400
            
            # Check if GitHub token is configured
            if not GITHUB_TOKEN:
                return jsonify({"ok": False, "code": "MISSING_TOKEN", "message": "GITHUB_TOKEN is not set. Provide a classic token with 'repo' or a fine-grained token with Pull Requests: Read."}), 500
            
            # Fetch PR diff
            diff_content = fetch_pr_diff(owner, repo, pr_number)
            if not diff_content:
                # Try fallback method
                diff_content = fetch_pr_diff_fallback(owner, repo, pr_number)
                if not diff_content:
                    return jsonify({"ok": False, "code": "FETCH_FAILED", "message": "Failed to fetch PR diff. Check token permissions or try again later."}), 500
            
            # Analyze with AI
            ai_result = analyze_with_ai(diff_content)
            if not ai_result:
                return jsonify({"ok": False, "code": "AI_FAILED", "message": "AI analysis failed"}), 500
            
            verdict = ai_result.get('verdict')
            comment = ai_result.get('comment')
            
            return jsonify({
                "ok": True,
                "verdict": verdict,
                "comment": comment,
                "pr_url": pr_url
            }), 200
            
        except Exception as e:
            print(f"Error in analyze PR endpoint: {str(e)}")
            return jsonify({"ok": False, "code": "INTERNAL_ERROR", "message": str(e)}), 500


    @app.route('/', methods=['GET'])
    def index():
        return send_from_directory('static', 'index.html')


    @app.route('/<path:path>')
    def static_files(path):
        return send_from_directory('static', path)


    @app.route('/status', methods=['GET'])
    def status():
        return jsonify({
            "service": "GitHub PR Triaging Agent",
            "status": "running",
            "webhook_endpoint": "/api/github-webhook",
            "integrations": {
                "gemini": "configured" if GEMINI_API_KEY else "missing GEMINI_API_KEY",
                "slack": "configured" if SLACK_BOT_TOKEN else "missing SLACK_BOT_TOKEN",
                "github": "configured" if GITHUB_TOKEN else "missing GITHUB_TOKEN"
            }
        }), 200


    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000, debug=False)