import os
import json
import requests
from flask import Flask, request, jsonify
from openai import OpenAI
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

app = Flask(__name__)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
slack_client = WebClient(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None

CHANNEL_MAPPING = {
    'CRITICAL': '#dev-urgent',
    'NEEDS_REVIEW': '#dev-main',
    'GOOD': '#dev-feed'
}

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


def fetch_diff(diff_url):
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
        if not openai_client:
            print("Warning: OpenAI client not initialized")
            return {"verdict": "NEEDS_REVIEW", "comment": "AI analysis unavailable - manual review required"}
        
        prompt = (
            "You are a senior developer acting as a code reviewer. "
            "Analyze this code diff and classify its severity. "
            "Respond only in a valid JSON format with two keys: "
            "1) 'verdict': (choose one: 'GOOD', 'NEEDS_REVIEW', or 'CRITICAL') "
            "and 2) 'comment': (your brief, one-sentence review)."
        )
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Code diff:\n\n{diff_content[:4000]}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result_text = response.choices[0].message.content
        if not result_text:
            return {"verdict": "NEEDS_REVIEW", "comment": "AI returned empty response"}
        result = json.loads(result_text)
        
        if 'verdict' not in result or 'comment' not in result:
            print(f"Warning: AI response missing required fields: {result}")
            return {"verdict": "NEEDS_REVIEW", "comment": "AI response incomplete - manual review required"}
        
        return result
        
    except Exception as e:
        print(f"Error in AI analysis: {str(e)}")
        return {"verdict": "NEEDS_REVIEW", "comment": f"AI analysis error - manual review required"}


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


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "service": "GitHub PR Triaging Agent",
        "status": "running",
        "webhook_endpoint": "/api/github-webhook",
        "integrations": {
            "openai": "configured" if OPENAI_API_KEY else "missing OPENAI_API_KEY",
            "slack": "configured" if SLACK_BOT_TOKEN else "missing SLACK_BOT_TOKEN",
            "github": "configured" if GITHUB_TOKEN else "missing GITHUB_TOKEN"
        }
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
