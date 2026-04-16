# Learn Hands On

Generate interactive hands-on labs from YouTube videos automatically. Extract transcripts, get AI summaries, and create personalized learning experiences.

## Project Structure

```
├── extension/              # Chrome extension
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.js
│   └── background.js
├── backend/                # Python Flask server
│   ├── app.py             # Main server code
│   ├── requirements.txt    # Python dependencies
│   ├── .env.local         # API keys (not committed)
│   ├── .env.example       # Environment template
│   └── .venv/             # Python virtual environment
└── README.md
```

## Getting Started

### 1. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local
# Edit .env.local and add your OPENAI_API_KEY
python3 app.py
```

Server runs on `http://localhost:3000` with auto-reload enabled.

### 2. Extension Setup

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select the `extension/` folder
5. The extension should now appear in your Chrome toolbar

## How It Works

1. User opens a YouTube video and clicks the extension
2. Optionally enters project context
3. Extension sends YouTube URL to backend
4. Backend extracts and summarizes the transcript using OpenAI
5. Summary appears in the extension popup
6. User can proceed with hands-on learning (next steps)

## Environment Variables

**Backend (.env.local):**
- `OPENAI_API_KEY` - Your OpenAI API key (required)

## Development

The Flask server runs in debug mode with auto-reload:
- Changes to `app.py` trigger automatic server restart
- All logs are shown in the terminal
