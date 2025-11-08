# GitHub PR Triaging Agent

An autonomous webhook service that receives GitHub pull request events, analyzes them with AI, and routes notifications to appropriate Slack channels based on severity.

## Features

- **Automated PR Analysis**: Uses OpenAI to review code diffs and classify severity
- **Smart Routing**: Routes notifications to different Slack channels based on AI verdict:
  - 🚨 **CRITICAL** → #dev-urgent (with @here mention)
  - 👀 **NEEDS_REVIEW** → #dev-main
  - ✅ **GOOD** → #dev-feed
- **Robust Error Handling**: Always returns 200 OK to GitHub to prevent webhook deactivation
- **Simple Setup**: Environment variable configuration with no database required
- **Dashboard UI**: Web interface to monitor service status and analyze PRs manually
- **Enhanced Diff Fetching**: Improved GitHub API integration with retry logic and fallback methods

## Setup Instructions

### 1. Configure Environment Secrets

You need to set up the following secrets. You can either use environment variables directly or use a `.env` file:

#### Using .env file (Recommended for local development)
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and fill in your actual values

#### Using Environment Variables
Set these environment variables in your system or Replit secrets:

#### OpenAI API Key
- Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
- Add secret: `OPENAI_API_KEY`

#### Slack Bot Token
- Create a Slack app at [Slack API](https://api.slack.com/apps)
- Add the following OAuth scopes:
  - `chat:write`
  - `chat:write.public`
- Install the app to your workspace
- Copy the "Bot User OAuth Token" (starts with `xoxb-`)
- Add secret: `SLACK_BOT_TOKEN`

#### GitHub Token (Required)
- Create a personal access token at [GitHub Settings](https://github.com/settings/tokens)
- Select scope: `repo` (for private repos) or `public_repo` (for public repos only)
- Add secret: `GITHUB_TOKEN`

### 2. Create Slack Channels

Make sure these channels exist in your Slack workspace:
- `#dev-urgent` - For critical PRs
- `#dev-main` - For PRs needing review
- `#dev-feed` - For approved PRs

Your Slack bot must be invited to all three channels.

### 3. Configure GitHub Webhook

1. Go to your GitHub repository → Settings → Webhooks → Add webhook
2. Set **Payload URL** to: `https://your-replit-url.repl.co/api/github-webhook`
3. Set **Content type** to: `application/json`
4. Select **Let me select individual events** and choose: `Pull requests`
5. Make sure the webhook is **Active**
6. Click **Add webhook`

## Dashboard UI

Access the dashboard at the root URL of your deployment to monitor the service status and analyze PRs:
```
GET https://your-replit-url.repl.co/
```

The UI allows you to manually analyze any GitHub PR by entering its URL.

## Testing

### Check Service Status
Visit the status endpoint to see the service status:
```
GET https://your-replit-url.repl.co/status
```

Response:
```json
{
  "service": "GitHub PR Triaging Agent",
  "status": "running",
  "webhook_endpoint": "/api/github-webhook",
  "integrations": {
    "openai": "configured",
    "slack": "configured",
    "github": "configured"
  }
}
```

### Test Webhook Locally
You can test the webhook with a sample payload:
```bash
curl -X POST https://your-replit-url.repl.co/api/github-webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -d '{
    "action": "opened",
    "pull_request": {
      "html_url": "https://github.com/user/repo/pull/1",
      "diff_url": "https://github.com/user/repo/pull/1.diff"
    }
  }'
```

### Test Diff Fetching
You can test the diff fetching functionality with the test script:
```bash
TEST_PR_URL=https://github.com/user/repo/pull/1 python scripts/test-diff.py
```

Or using the project script:
```bash
TEST_PR_URL=https://github.com/user/repo/pull/1 pipx run repl-nix-workspace test-diff
```

## How It Works

1. **GitHub sends webhook** when a PR is opened
2. **Webhook endpoint** validates it's a `pull_request` event with `opened` action
3. **Fetch diff** from GitHub using enhanced authenticated connector with retry logic
4. **AI Analysis** with OpenAI:
   - Analyzes the code diff
   - Classifies as GOOD, NEEDS_REVIEW, or CRITICAL
   - Provides a brief review comment
5. **Slack notification** sent to appropriate channel based on verdict
6. **Response** returned to GitHub (always 200 OK to prevent webhook deactivation)

## Enhanced Diff Fetching

The agent now includes improved diff fetching with:

- **Proper GitHub API integration** using the correct Accept header
- **Authentication** with Authorization: Bearer token
- **Retry logic** with exponential backoff on 429/5xx errors
- **Rate limit handling** with proper waiting
- **Fallback method** using the raw diff endpoint
- **Input validation** for PR URLs
- **Clear error messages** for different failure modes

## Error Handling

The service is designed to never fail from GitHub's perspective:
- All errors are caught and logged
- Always returns 200 OK to GitHub
- Falls back gracefully if AI or Slack is unavailable
- Detailed error logging for debugging

## Development

The server runs on port 5000 and is configured to bind to `0.0.0.0` to accept external connections.

To view logs, check the Flask Server workflow in the Replit console.

## Security Notes

- Never commit API keys or tokens to the repository
- All secrets should be configured via Replit environment variables or .env file
- The GitHub token is required for diff fetching
- Slack bot should only have minimal required permissions

## Troubleshooting

**Webhook not receiving events:**
- Check that the webhook URL is correct in GitHub settings
- Verify the webhook is Active
- Check that "Pull requests" event is selected

**Slack messages not sending:**
- Verify SLACK_BOT_TOKEN is correct
- Make sure the bot is invited to all three channels
- Check that bot has `chat:write` and `chat:write.public` scopes

**AI analysis failing:**
- Verify OPENAI_API_KEY is set correctly
- Check OpenAI API status and your account credits
- Service will fall back to "NEEDS_REVIEW" if AI fails

**Diff fetching failing:**
- Verify GITHUB_TOKEN is set correctly
- Check that the token has appropriate scopes (`repo` or fine-grained "Pull requests: Read")
- Try the test script to debug: `TEST_PR_URL=... python scripts/test-diff.py`