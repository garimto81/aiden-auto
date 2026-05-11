---
name: slack
description: >
  Slack messaging skill. Browser OAuth authentication, message send/receive, channel management.
  Use when requests mention "slack", "슬랙 메시지", or "slack 전송".
version: 1.0.0
triggers:
  keywords:
    - "slack"
    - "슬랙"
    - "slack message"
    - "슬랙 메시지"
    - "send to slack"
    - "slack 전송"
    - "slack 채널"
    - "slack login"
    - "slack 인증"
  patterns:
    - "slack (login|send|history|channels|user|status)"
    - "슬랙.*(보내|전송|읽|채널)"
  file_patterns:
    - "**/slack*.py"
    - "**/slack_*.json"
  context:
    - "Slack integration"
    - "Channel messaging"
    - "Team communication"
capabilities:
  - slack_oauth
  - send_message
  - read_history
  - list_channels
  - get_user_info
model_preference: sonnet
auto_trigger: true
---

# Slack Skill

Slack API integration skill. Provides Browser OAuth 2.0 authentication, message send/receive, and channel management.

## Prerequisites

### 1. Create a Slack App

1. Visit https://api.slack.com/apps
2. "Create New App" > "From scratch"
3. Enter App Name, select Workspace
4. Navigate to "OAuth & Permissions"

### 2. Configure Redirect URL

On the **OAuth & Permissions** page, add to the **Redirect URLs** section:
```
http://localhost:8765/slack/oauth/callback
```

### 3. Configure OAuth Scopes

Add the following Bot Token Scopes:
- `chat:write` - Send messages
- `channels:read` - Public channel list
- `channels:history` - Public channel history
- `groups:read` - Private channel list
- `groups:history` - Private channel history
- `im:write` - Send DMs
- `users:read` - User info

### 4. Save Credentials

Create the file `C:\claude\json\slack_credentials.json`.

**Option A: Enter Bot Token directly (recommended - simpler)**

```json
{
  "bot_token": "xoxb-YOUR-BOT-TOKEN"
}
```

Copy the Bot Token from the **Bot User OAuth Token** at the top of the **OAuth & Permissions** page.

**Option B: OAuth authentication (browser popup)**

```json
{
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}
```

Client ID/Secret are available on the "Basic Information" page.

### 5. Run Authentication

```powershell
python -m lib.slack login
```

- **Bot Token method**: Validates immediately and completes
- **OAuth method**: Browser opens, Slack authenticates, and the token is saved automatically

## Commands

| Command | Description |
|---------|-------------|
| `python -m lib.slack login` | OAuth authentication (one-time) |
| `python -m lib.slack status` | Check auth status |
| `python -m lib.slack send <channel> <message>` | Send message |
| `python -m lib.slack update <channel> <ts> <message>` | Update existing message |
| `python -m lib.slack history <channel>` | Message history |
| `python -m lib.slack channels` | Channel list |
| `python -m lib.slack user <user_id>` | User info |
| `python -m lib.slack list-items <list_id>` | Query Slack List items |
| `python -m lib.slack list-add <list_id> <title>` | Add item to Slack List |

## Usage Examples

### Send Message

```powershell
# Send message to channel
python -m lib.slack send "#general" "Hello, world!"

# Reply in thread
python -m lib.slack send "C01234567" "Reply" --thread "1234567890.123456"
```

### Read Messages

```powershell
# Last 10 messages
python -m lib.slack history "#general" --limit 10

# Default 100
python -m lib.slack history "C01234567"
```

### Channel List

```powershell
# Public channels only
python -m lib.slack channels

# Include private
python -m lib.slack channels --private
```

## Python API

```python
from lib.slack import SlackClient, login, get_token

# Authenticate (one-time)
login()

# Create client
client = SlackClient()

# Send message
result = client.send_message("#general", "Hello!")
print(result.permalink)

# Read history
messages = client.get_history("#general", limit=10)
for msg in messages:
    print(f"{msg.user}: {msg.text}")

# Channel list
channels = client.list_channels(include_private=True)
for ch in channels:
    print(f"#{ch.name} ({ch.id})")
```

## Claude Mandatory Execution Rules (MANDATORY)

**When a Slack keyword is detected, Claude MUST automatically perform the following.**

### Step 1: Check Auth Status (always first)

```powershell
cd C:\claude && python -m lib.slack status --json
```

**Interpreting the result:**
- `"authenticated": true, "valid": true` → proceed to Step 2
- `"authenticated": false` → guide the user to log in:
  ```
  Slack authentication is required. Run the following command:
  python -m lib.slack login
  ```

### Step 2: Run the Command for the Request

| User Request | Command to Run |
|--------------|----------------|
| "Show channel list" | `python -m lib.slack channels --json` |
| "Include private channels" | `python -m lib.slack channels --private --json` |
| "Send a message" | `python -m lib.slack send "#channel" "message"` |
| "Read messages" | `python -m lib.slack history "channel" --limit 20 --json` |
| "User info" | `python -m lib.slack user "U12345" --json` |
| "Analyze Slack" | List channels, then analyze history per channel |

### Step 3: Parse JSON Result and Respond

Parse the `--json` flag output and respond to the user in a readable format.

**Example - channel list:**
```json
{"count": 5, "channels": [{"id": "C123", "name": "general", ...}]}
```
→ "There are 5 channels: #general, #random, ..."

### Required Behavior (MUST)

| Rule | Description |
|------|-------------|
| ✅ Prefix with `cd C:\claude &&` | Run module from project root |
| ✅ Use `--json` flag | Easier to parse |
| ✅ Use Bash tool directly | Run lib/slack CLI |
| ✅ Provide detailed guidance on errors | Auth setup, bot invite, etc. |

### Prohibited Behavior (NEVER)

| Prohibited | Reason |
|------------|--------|
| ❌ Read slack_token.json directly | Security risk |
| ❌ Call Slack API via WebFetch | Requires OAuth token |
| ❌ Respond "no infrastructure" | CLI can be invoked directly via Bash |
| ❌ Ask user to run commands manually | Claude runs them directly |

### Channel Analysis Workflow

When the user requests "Slack analysis" or "channel analysis":

```powershell
# 1. Full channel list
cd C:\claude && python -m lib.slack channels --private --json

# 2. Recent messages per channel (e.g., top 3 channels)
python -m lib.slack history "C_channel_id_1" --limit 50 --json
python -m lib.slack history "C_channel_id_2" --limit 50 --json

# 3. Aggregate results and write an analysis report
```

## Workflow (Legacy)

When the user makes a Slack-related request:

1. **Check token**: run `python -m lib.slack status --json`
2. **If missing**: guide with `python -m lib.slack login`
3. **If present**: run requested action (with `--json` flag)
4. **Output result**: parse JSON and respond in a readable form

## Error Handling

| Error | Solution |
|-------|----------|
| `SlackCredentialsNotFoundError` | Need to create slack_credentials.json |
| `SlackAuthError` | Re-run `python -m lib.slack login` |
| `SlackRateLimitError` | Retry later (auto-waits) |
| `SlackChannelNotFoundError` | Check channel ID or invite the bot |

## File Locations

| File | Purpose |
|------|---------|
| `C:\claude\json\slack_credentials.json` | OAuth app credentials (user-created) |
| `C:\claude\json\slack_token.json` | Access token (auto-generated) |
| `C:\claude\lib\slack\` | Library source code |

## Rate Limits

Complies with Slack API 2026 Rate Limits:
- `chat.postMessage`: 3s interval
- `conversations.history`: 1.2s interval
- `conversations.list`: 3s interval
- `users.info`: 0.6s interval

Rate limiting is applied automatically.
