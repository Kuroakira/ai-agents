# Memo Observer Agent

An AI agent that analyzes memos and thoughts received from Slack and automatically adds them to a Notion Database.

## Overview

- **Input**: Text messages to Slack (voice-to-text thoughts, Kindle highlights, etc.)
- **Processing**: Analyzes text with Gemini 2.5 Flash, extracts dynamic tags and content
- **Output**: Creates pages in Notion database

## Feature: Dynamic Tag System

Instead of fixed categories, **AI dynamically generates tags based on content**.

- Automatically generates 1-3 specific tags representing the content
- Reuses existing tags when available ("AI Agent" and "AIエージェント" are treated as same)
- Creates new tags for new concepts
- Examples: "AI Agent", "Organization", "LangGraph", "Book Notes"

## Architecture

```mermaid
graph TD;
    __start__([__start__])
    fetch_tags(fetch_tags<br/>Get Existing Tags)
    parser(parser<br/>Text Analysis)
    tag_matcher(tag_matcher<br/>Tag Matching)
    saver(saver<br/>Save to Notion)
    __end__([__end__])
    __start__ --> fetch_tags;
    fetch_tags --> parser;
    parser --> tag_matcher;
    tag_matcher --> saver;
    saver --> __end__;
```

### Flow Description

1. **fetch_tags**: Retrieve existing tags from Notion
2. **parser**: Analyze text with LLM, generate tag candidates considering existing tags
3. **tag_matcher**: Match candidate tags with existing tags using similarity detection
4. **saver**: Save to Notion with final tags

## Directory Structure

```
agents/memo/
├── __init__.py              # Package initialization
├── state.py                 # State schema (MemoState)
├── schema.py                # LLM output schema (MemoItem)
├── nodes.py                 # Node functions (fetch_tags, parser, tag_matcher, saver)
├── graph.py                 # LangGraph workflow
├── tools.py                 # Notion API integration + tag similarity
├── slack_app.py             # Slack Bot integration
├── slack_app_manifest.yaml  # Slack App Manifest
├── example.py               # Demo script
├── README.md                # Japanese documentation
└── README.en.md             # This file
```

---

## Setup

### 1. Google Gemini API

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Click **Create API Key**
3. Copy the API key → set in `.env`

```bash
GOOGLE_API_KEY=your_gemini_api_key
```

### 2. Notion Integration

#### 2.1 Create Integration

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click **New integration**
3. Configure:
   - **Name**: `Memo Observer`
   - **Associated workspace**: Select your workspace
   - **Capabilities**:
     - ✅ Read content
     - ✅ Insert content
     - ✅ Update content
4. **Submit** → Copy **Internal Integration Secret**

```bash
MEMO_NOTION_TOKEN=secret_xxxxxxxxxxxxx
```

#### 2.2 Create Database

1. Create a new page in Notion
2. Type `/database` → Select **Database - Full page**
3. Set database name (e.g., `Memos`)

#### 2.3 Configure Properties

Add the following properties (**pre-configuration required**):

| Property Name | Type | How to Set |
|--------------|------|------------|
| Name | Title | Exists by default (no change needed) |
| Category | Multi-select | `+` → Select **Multi-select** |
| Source | Text | `+` → Select **Text** |
| Created | Date | `+` → Select **Date** |

**About Category**:
- Use Multi-select type (supports multiple tags)
- No initial options needed (AI creates them dynamically)
- Tags will automatically grow as you use it

#### 2.4 Connect Integration

1. Click `•••` at the top right of the database page
2. **Connections** → **Connect to** → Select `Memo Observer`

#### 2.5 Get Database ID

Get the ID from the browser URL:

```
https://www.notion.so/yourworkspace/abc123def456789012345678901234?v=xyz
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                    This part is the Database ID
```

You can also use the full URL (ID will be extracted automatically):

```bash
MEMO_NOTION_DB_ID=https://www.notion.so/yourworkspace/abc123def456...
# or
MEMO_NOTION_DB_ID=abc123def456789012345678901234
```

### 3. Slack App

#### 3.1 Create with Manifest (Recommended)

1. Go to [Slack API](https://api.slack.com/apps) → **Create New App**
2. Select **From an app manifest**
3. Select your workspace
4. Paste the contents of `slack_app_manifest.yaml`
5. Click **Create**

#### 3.2 Get App-Level Token

1. **Basic Information** → **App-Level Tokens**
2. **Generate Token and Scopes**
   - Token Name: `socket-mode`
   - Scope: Add `connections:write`
3. **Generate** → Copy the `xapp-...` token

```bash
MEMO_SLACK_APP_TOKEN=xapp-1-xxxxxxxxxxxxx
```

#### 3.3 Get Bot Token

1. **OAuth & Permissions** → **Install to Workspace**
2. Click **Allow**
3. Copy the **Bot User OAuth Token** (`xoxb-...`)

```bash
MEMO_SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxxxx
```

#### 3.4 Add Bot to Channel

1. Open the channel where you want to send memos
2. Click channel name → **Integrations** tab
3. **Add apps** → Add `Memo Observer`

---

## Environment Variables Summary

`.env` file:

```bash
# Google Gemini API
GOOGLE_API_KEY=your_gemini_api_key

# Notion Integration
MEMO_NOTION_TOKEN=secret_xxxxxxxxxxxxx
MEMO_NOTION_DB_ID=your_database_id_or_url

# Slack Bot (Socket Mode)
MEMO_SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxxxx
MEMO_SLACK_APP_TOKEN=xapp-1-xxxxxxxxxxxxx
```

---

## Input Patterns

### 1. Regular Thought Memos

```
I was thinking about AI agent design today.
Using LangGraph makes state management simpler.
```

→ Tag examples: `AI Agent`, `LangGraph`, `Design`

### 2. Kindle Highlights

```
"Knowledge is power" - Francis Bacon, Novum Organum
```

→ Tag examples: `Book Notes`, `Philosophy`, `Quotes`

---

## Tag Similarity Detection

The following cases are treated as the same tag:

| Candidate Tag | Existing Tag | Result |
|--------------|--------------|--------|
| `AI Agent` | `ai agent` | Use existing |
| `AIエージェント` | `ＡＩエージェント` | Use existing |
| `Lang Graph` | `langgraph` | Use existing |

Normalization rules:
- Full-width alphanumeric → Half-width
- Uppercase → Lowercase
- Consecutive spaces → Single space

---

## Usage

### Demo Script

```bash
# Run with sample memos
python -m agents.memo.example

# Interactive mode
python -m agents.memo.example --interactive
```

### Start Slack Bot

```bash
python -m agents.memo.slack_app
```

### Use from Code

```python
import asyncio
from dotenv import load_dotenv
from agents.memo.graph import app
from agents.memo.state import MemoState

async def main():
    load_dotenv()

    state = MemoState(input_text="Today I learned: how to use LangGraph")
    result = await app.ainvoke(state)

    print(f"Status: {result.get('status')}")
    print(f"Tags: {result.get('final_tags')}")
    print(f"Notion URL: {result.get('notion_url')}")

asyncio.run(main())
```

---

## Troubleshooting

### Notion API Errors

**"Could not find property with name..."**
→ Property doesn't exist in the database. Check [Property Configuration](#23-configure-properties).

**"Could not find database..."**
→ Database ID is incorrect or Integration is not connected.

### Slack Bot Not Responding

1. Verify Socket Mode is enabled
2. Check if events are subscribed in Event Subscriptions
3. Confirm Bot is added to the channel

---

## Future Enhancements

- [ ] Human-in-the-loop confirmation flow
- [ ] Batch processing of multiple memos
- [x] ~~Automatic tag generation~~ ✅ Implemented
- [ ] Similar memo search and linking
- [ ] Periodic tag cleanup (merging similar tags)
