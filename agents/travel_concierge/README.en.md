# Travel Concierge Agent

Travel planning AI agent with interview and research capabilities.

## Overview

An agent that interviews users about their travel wishes through natural conversation, autonomously performs web research once requirements are gathered, and outputs the results to Notion in an easy-to-compare "travel magazine" format.

## Architecture

```mermaid
graph TD;
    __start__([__start__])
    interview(interview<br/>Gather requirements)
    research(research<br/>Web research)
    publish(publish<br/>Notion output)
    __end__([__end__])
    __start__ --> interview;
    interview -->|incomplete| interview;
    interview -->|complete| research;
    research --> publish;
    publish --> __end__;
```

## Features

- **Interview**: Collect travel requirements through natural conversation (destination, timing, travelers, preferences)
- **Web Research**: Search for timing trends, price estimates, and accommodations using Tavily API
- **Notion Output**: Automatically create travel plan articles in database

## Setup

### 1. Environment Variables

Add the following to your `.env` file in the project root:

```bash
# Google Gemini API Key (for LLM)
GOOGLE_API_KEY=your_gemini_api_key

# Tavily API Key (for web search)
# Get from https://tavily.com/
TAVILY_API_KEY=your_tavily_api_key

# Notion API Key
# Get from https://www.notion.so/my-integrations
NOTION_API_KEY=your_notion_api_key

# Notion Database ID (output destination)
# Set database URL or ID
NOTION_DATABASE_ID=your_database_id_or_url

# User's location (for flight search, default: Tokyo)
USER_LOCATION=Tokyo

# Slack Bot Token (Travel Concierge specific)
TRAVEL_SLACK_BOT_TOKEN=xoxb-your-bot-token
TRAVEL_SLACK_APP_TOKEN=xapp-your-app-token
```

### 2. Slack App Setup

Create a separate Slack App from other agents.

#### 2.1 Create Slack App

1. Go to [Slack API](https://api.slack.com/apps) and click "Create New App" → "From scratch"
2. App name: `Travel Concierge`, select your workspace

#### 2.2 Enable Socket Mode

1. Go to "Socket Mode" → Enable Socket Mode to ON
2. Click "Generate" → Copy the App Token (`xapp-...`) → `TRAVEL_SLACK_APP_TOKEN`

#### 2.3 Configure with App Manifest

```yaml
display_information:
  name: Travel Concierge
  description: Travel Concierge AI - Helps you plan your trips
  background_color: "#2eb886"
features:
  app_home:
    home_tab_enabled: true
    messages_tab_enabled: true
    messages_tab_read_only_enabled: false
  bot_user:
    display_name: Travel Concierge
    always_online: true
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - im:history
      - im:read
      - im:write
settings:
  event_subscriptions:
    bot_events:
      - app_home_opened
      - app_mention
      - message.im
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```

#### 2.4 Install App

Go to "Install App" → "Install to Workspace"
Copy the Bot User OAuth Token (`xoxb-...`) → `TRAVEL_SLACK_BOT_TOKEN`

### 3. Notion Setup

#### 3.1 Create Integration

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click "New integration"
3. Enter a name (e.g., Travel Concierge)
4. Click "Submit" → Copy the **Internal Integration Secret**

#### 3.2 Create Database and Connect

1. Create a new full-page database in Notion (select "Table" when creating a new page)
2. Click "..." in the top right of the database page → "Connections" → Add your integration
3. Copy the database URL and set it as `NOTION_DATABASE_ID`

### 4. Install Dependencies

```bash
pip install -e ".[dev]"
```

## Usage

### Slack Bot

```bash
python -m agents.travel_concierge.slack_app
```

Mention the bot in a channel like `@Travel Concierge I want to go to Hokkaido` to start a conversation in a thread.

### Console Chat

```bash
python -m agents.travel_concierge.example
```

### Demo Mode (Interview Only)

```bash
python -m agents.travel_concierge.example --demo
```

### Input Example

```
I want to travel to Hokkaido
↓
Around Golden Week, late April to early May
↓
2 adults and 2 kids, ages 5 and 2
↓
I'd like a Japanese-style room with futon, and want to eat crab!
```

### Output Example

An article like the following is automatically created in Notion:

```
✈️ Hokkaido Family Trip Plan

📋 Travel Conditions
• Destination: Hokkaido
• Timing: Around Golden Week
• Travelers: 2 adults, 2 children (ages 5 and 2)
• Preferences: Japanese room, futon, crab cuisine

📅 Best Timing and Prices
• Mid-April - ¥25,000〜¥35,000
  Advantages: Less crowded, cherry blossoms in season
  Disadvantages: Unstable weather

🏨 Recommended Accommodations
• ○○ Ryokan
  Features: Japanese rooms, famous for crab cuisine
  💡 A quiet inn perfect for families
```

## File Structure

```
agents/travel_concierge/
├── __init__.py      # Package initialization
├── state.py         # State schema (Pydantic)
├── tools.py         # Tavily/Notion API operations
├── nodes.py         # Node functions (including LLM)
├── graph.py         # LangGraph workflow
├── slack_app.py     # Slack Bot integration
├── example.py       # Console example
├── README.md        # Japanese documentation
└── README.en.md     # English documentation
```

## Parameters

### TravelContext (Collected Information)

| Parameter | Type | Description |
|-----------|------|-------------|
| destination | str | Destination |
| timing | str | Timing (can be vague) |
| travelers | Travelers | Traveler composition (adults, children, notes) |
| constraints | list[str] | Preferences/requirements |

### Output (TravelConciergeState)

| Parameter | Type | Description |
|-----------|------|-------------|
| research_result | ResearchResult | Research results (timing, accommodations) |
| notion_page_url | str | Created Notion page URL |
| response_text | str | Response message to user |

## Troubleshooting

### TAVILY_API_KEY Error

Get an API key from [Tavily](https://tavily.com/) and set it in `.env`.

### NOTION_API_KEY Error

Create an integration at [Notion Integrations](https://www.notion.so/my-integrations) and get the API key.

### Page Not Created in Notion

- Verify the integration is connected to the database
- Verify the database ID is correct

## License

MIT
