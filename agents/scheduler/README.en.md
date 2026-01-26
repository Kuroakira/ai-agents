# Scheduler Agent

Brain dump organizer & calendar registration AI agent.

## Overview

An agent that receives miscellaneous tasks (brain dump) from Slack and automatically schedules them in Google Calendar's available time slots.

## Architecture

```mermaid
graph TD;
    __start__([__start__])
    fetch_calendar_events(fetch_calendar_events<br/>Fetch today's events)
    analyze_tasks(analyze_tasks<br/>Extract tasks with LLM)
    schedule_tasks(schedule_tasks<br/>Register to calendar)
    generate_response(generate_response<br/>Generate response)
    __end__([__end__])
    __start__ --> fetch_calendar_events;
    fetch_calendar_events --> analyze_tasks;
    analyze_tasks --> schedule_tasks;
    schedule_tasks --> generate_response;
    generate_response --> __end__;
```

## Features

- **Task Extraction**: Automatically identifies tasks from natural language
- **Duration Estimation**: Estimates appropriate time based on task content
- **Free Slot Detection**: Calculates available time slots from Google Calendar
- **Auto Scheduling**: Places tasks at preferred time or available slots
- **Slack Integration**: Runs persistently in Socket Mode for instant responses

## Setup

### 1. Google Cloud Configuration (Calendar API)

Google Calendar API uses OAuth 2.0 authentication.

#### 1.1 Create Project and Enable API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Left menu: "APIs & Services" → "Library"
4. Search for "Google Calendar API" and click "Enable"

#### 1.2 Configure OAuth Consent Screen

1. Left menu: "APIs & Services" → "OAuth consent screen"
2. User Type: Select **External** and click "Create"
3. Fill in app information:
   - App name: Any name (e.g., Scheduler Bot)
   - User support email: Your email address
   - Developer contact: Your email address
4. Click "Save and Continue" → Skip scopes → "Save and Continue"
5. Add **your Gmail address** as a test user → "Save and Continue"

#### 1.3 Create Credentials

1. Left menu: "APIs & Services" → "Credentials"
2. "Create Credentials" → "OAuth client ID"
3. Application type: **Desktop app**
4. Name: Any name (e.g., Scheduler Bot Desktop)
5. Click "Create" → Download JSON
6. Place the downloaded file as **`credentials.json`** in the project root

### 2. Slack App Configuration

#### 2.1 Create App

1. Go to [Slack API](https://api.slack.com/apps)
2. "Create New App" → Select "**From scratch**"
3. App Name: Any name (e.g., Scheduler Bot)
4. Workspace: Select your workspace
5. Click "Create App"

#### 2.2 Enable Socket Mode and Get App Token

1. Left menu: "Socket Mode"
2. Turn ON "Enable Socket Mode"
3. Token Name: Any name (e.g., scheduler-socket)
4. Click "Generate" → Copy and save the **App Token (`xapp-...`)**

#### 2.3 Configure with App Manifest (Recommended)

1. Left menu: "App Manifest"
2. Replace the content in the YAML tab with:

```yaml
display_information:
  name: Scheduler Bot
features:
  bot_user:
    display_name: Scheduler Bot
    always_online: false
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - im:history
      - im:read
      - reactions:read
      - reactions:write
settings:
  event_subscriptions:
    bot_events:
      - app_mention
      - message.im
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```

3. Click "Save Changes"

#### 2.4 Install App and Get Bot Token

1. Left menu: "Install App"
2. Click "Install to Workspace" → "Allow"
3. Copy and save the **Bot User OAuth Token (`xoxb-...`)**

### 3. Environment Variables

Create a `.env` file in the project root:

```bash
# Google Gemini API Key (for LLM)
# Get from https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=your_gemini_api_key

# Slack Bot Token (from OAuth & Permissions)
SLACK_BOT_TOKEN=xoxb-your-bot-token

# Slack App Token (from Socket Mode setup)
SLACK_APP_TOKEN=xapp-your-app-token

# LangChain Tracing (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langchain_api_key
```

#### Authentication Methods

| Purpose | Auth Method | Required |
|---------|-------------|----------|
| Google Calendar API | OAuth 2.0 | `credentials.json` + `token.json` (auto-generated) |
| Google Gemini (LLM) | API Key | `GOOGLE_API_KEY` environment variable |
| Slack Bot | Token | `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` |

### 4. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 5. Initial Authentication (Google Calendar)

On first run, a browser will open requesting Google account authentication.

1. Click "Continue"
2. Select your Google account
3. If "This app isn't verified" appears, click "Advanced" → "Go to (app name)"
4. Click "Allow"

After successful authentication, `token.json` is automatically generated in the project root.

## Usage

### Start Slack Bot

```bash
python -m agents.scheduler.slack_app
```

### Local Test (without Slack)

```bash
python -m agents.scheduler.example
```

### Input Example

```
Review meeting materials at 10, and I need to buy milk. Going to the gym in the evening.
```

### Output Example

```
✅ The following tasks have been registered to calendar:

• 10:00〜10:30: 📝Review meeting materials
• 12:00〜12:30: 📝Buy milk
• 19:00〜20:30: 📝Go to gym
```

## File Structure

```
agents/scheduler/
├── __init__.py      # Package initialization
├── state.py         # State schema (Pydantic)
├── tools.py         # Google Calendar API operations
├── nodes.py         # Node functions (including LLM)
├── graph.py         # LangGraph workflow
├── slack_app.py     # Slack Bot integration
├── example.py       # Usage example
├── README.md        # Japanese documentation
└── README.en.md     # English documentation
```

## Parameters

### Input (SchedulerState)

| Parameter | Type | Description |
|-----------|------|-------------|
| user_input | str | User input message |
| user_id | str | Slack user ID |
| channel_id | str | Slack channel ID |

### Output (SchedulerState)

| Parameter | Type | Description |
|-----------|------|-------------|
| response_text | str | Response message to user |
| scheduled_events | list[CalendarEvent] | List of registered events |
| extracted_tasks | list[TaskItem] | List of extracted tasks |
| error_message | str \| None | Error message |

## Configuration

### Working Hours

By default, 9:00-21:00 is used as working hours for calculating free slots.
To change, modify `calculate_free_slots()` in `tools.py`.

### Task Name Prefix

Registered tasks are prefixed with "📝".
To change, modify the system prompt in `nodes.py`.

## Troubleshooting

### credentials.json not found

Re-download from Google Cloud Console.

### token.json authentication error

Delete `token.json` and re-authenticate.

### Slack not responding

- Verify Bot Token and App Token are correct
- Verify Socket Mode is enabled
- Verify Event Subscriptions are properly configured

## License

MIT
