# Backend Server

Python Flask server that extracts YouTube transcripts and generates AI summaries for hands-on learning.

## Setup

1. Create virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create `.env.local` with your OpenAI API key:
   ```bash
   cp .env.example .env.local
   # Edit .env.local and add your OPENAI_API_KEY
   ```

4. Start the server (with auto-reload):
   ```bash
   python3 app.py
   ```

The server will run on `http://localhost:3000` with debug mode enabled.

## API Endpoints

### POST `/api/generate-lab`
Extract and summarize a YouTube video transcript.

**Request:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=...",
  "project_context": "Optional: I'm learning Docker for DevOps"
}
```

**Response:**
```json
{
  "success": true,
  "labId": "lab_1234567890",
  "summary": "This tutorial teaches...",
  "project_context": "Optional context provided"
}
```

### GET `/health`
Health check endpoint.

## Environment Variables

- `OPENAI_API_KEY` - Your OpenAI API key (required)

## Dependencies

See `requirements.txt`:
- Flask - Web framework
- Flask-CORS - CORS support
- openai - OpenAI API client
- youtube-transcript-api - YouTube transcript extraction

## Development Features

- **Debug Mode**: Enabled by default
- **Auto-Reload**: Server restarts automatically on code changes
- **Live Logs**: All activity logged to console
