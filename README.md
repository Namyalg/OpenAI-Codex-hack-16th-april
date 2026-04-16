# Learn Hands On 🎓

Transform YouTube tutorials into interactive, hands-on learning labs. Automatically extract transcripts, generate AI-powered summaries, create personalized Docker environments, and learn by doing.

## 🎯 Overview

**Learn Hands On** is an AI-powered educational platform that bridges the gap between passive video watching and active learning. Simply click on any YouTube video, and the system instantly creates a customized Docker environment with all the tools you need to follow along with the tutorial hands-on.

### Key Features

- **Automatic Lab Generation**: Extract transcripts from YouTube videos automatically
- **AI-Powered Summaries**: Get concise summaries of video content using GPT
- **Personalized Environment**: AI generates Dockerfiles tailored to the tutorial content
- **Interactive Learning**: Execute commands in real-time within a containerized environment
- **AI Learning Companion**: Ask questions and get contextual guidance as you learn
- **Step-by-Step Guidance**: AI-generated learning steps that adapt based on your actions

---

## 📋 Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     CHROME EXTENSION                              │
│  (Runs in Browser)                                                │
│  • Detects YouTube videos                                         │
│  • Orchestrates 3-step lab creation flow                         │
│  • Displays loading states and feedback                           │
└──────────────────────┬───────────────────────────────────────────┘
                       │ HTTP Requests (CORS)
                       ↓
┌──────────────────────────────────────────────────────────────────┐
│                  FLASK BACKEND SERVER (Python)                    │
│  • REST API endpoints for lab management                          │
│  ┌──────────────────┬──────────────────┬──────────────────────┐  │
│  │ Step 1: Extract  │ Step 2: Generate │ Step 3: Build & Run  │  │
│  │ & Summarize      │ Dockerfile       │ Docker Container     │  │
│  ├──────────────────┼──────────────────┼──────────────────────┤  │
│  │ • YouTube API    │ • OpenAI GPT-4o  │ • Docker Build/Run   │  │
│  │ • Transcripts    │ • Package Validation │ • Subprocess Exec  │  │
│  │ • GPT Summary    │ • Retry Logic (3x)   │                    │  │
│  └──────────────────┴──────────────────┴──────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │     Lab Session Manager (In-Memory State)                  │  │
│  │  • Tracks running containers                               │  │
│  │  • Stores learning progress                                │  │
│  │  • Maintains conversation history                          │  │
│  │  • Records executed commands                               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────┬────────────┬──────────────┬─────────────────┐  │
│  │ API: /health │ /api/*     │ /lab         │ /api/lab/<id>/* │  │
│  └──────────────┴────────────┴──────────────┴─────────────────┘  │
└──────────────┬─────────────┬──────────────┬────────────────────┘
               │             │              │
        ┌──────┴─┐    ┌──────┴─┐    ┌──────┴──┐
        ↓        ↓    ↓        ↓    ↓         ↓
    ┌────────┐ ┌──────┐ ┌──────────┐ ┌──────────┐
    │ Docker │ │ OpenAI │ │ YouTube │ │ External │
    │ Engine │ │  API  │ │   API   │ │ Package  │
    │        │ │ (GPT) │ │(Transcr.)│ │Repos    │
    └────────┘ └──────┘ └──────────┘ └──────────┘
```

### System Flow

```
1. USER INITIATES LAB
   └─ Clicks extension icon on YouTube video

2. STEP 1: EXTRACT & SUMMARIZE (generate-lab)
   ├─ Extract video ID from YouTube URL
   ├─ Fetch transcript using YouTube Transcript API
   ├─ Summarize using OpenAI GPT-4o-mini (300 tokens)
   └─ Generate secure lab_id

3. STEP 2: GENERATE DOCKERFILE (start-lab)
   ├─ Generate Dockerfile using GPT-4o-mini
   ├─ Validate packages against:
   │  ├─ Ubuntu 22.04 official repositories
   │  └─ PyPI (Python Package Index)
   ├─ Retry up to 3 times if validation fails
   └─ Return validated Dockerfile

4. STEP 3: BUILD & RUN (build-lab)
   ├─ Create temporary directory
   ├─ Write Dockerfile to temp directory
   ├─ Build Docker image with unique tag
   ├─ Start container (detached, interactive mode)
   ├─ Store lab session in memory
   └─ Return lab URL

5. INTERACTIVE SESSION (lab.html)
   ├─ Display embedded YouTube video
   ├─ Show initial learning step from AI
   ├─ Provide terminal for command execution
   ├─ Display real-time command output
   ├─ Generate next steps dynamically (next-step endpoint)
   └─ Support AI Q&A for clarification

6. COMMAND EXECUTION (/api/lab/<lab_id>/execute)
   ├─ Execute command in running container
   ├─ Capture stdout/stderr
   ├─ Store command in history
   ├─ Generate contextual next step
   └─ Return output and next step

7. Q&A SUPPORT (/api/lab/<lab_id>/ask)
   ├─ Accept user question
   ├─ Generate answer using GPT with context
   ├─ Store Q&A in conversation history
   └─ Return answer
```

---

## 📦 Prerequisites

### System Requirements

- **Docker**: Running locally (required to build and execute lab environments)
  - Installation: https://docs.docker.com/get-docker/
  - Verify: `docker --version`

- **Python 3.8+**: For running the Flask backend
  - Installation: https://www.python.org/downloads/
  - Verify: `python3 --version`

- **Chrome Browser**: For the extension
  - Version 88+ recommended for Manifest V3 support

- **OpenAI API Key**: For AI features (transcript summary, Dockerfile generation, learning steps)
  - Sign up: https://platform.openai.com/signup
  - Create API key: https://platform.openai.com/account/api-keys
  - Estimated usage: ~$0.10-0.50 per lab (depends on transcript length)

### Network Requirements

- **Backend Server**: Requires internet access to:
  - OpenAI API endpoints
  - YouTube.com (for transcript extraction)
  - Ubuntu package repositories
  - PyPI (Python packages registry)

---

## 🚀 Quick Start

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create Python virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate    # On macOS/Linux
# or
.venv\Scripts\activate        # On Windows

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env.local

# Edit .env.local and add your OpenAI API key
# OPENAI_API_KEY=sk-your-key-here
nano .env.local  # or use your editor
```

**Start the server:**

```bash
python3 app.py
```

Server runs on `http://localhost:3000` with auto-reload enabled.

**Expected output:**
```
[Init] Starting server...
[Init] OpenAI API Key: Set
[Init] Debug mode enabled - server will auto-reload on file changes
 * Running on http://localhost:3000
```

### 2. Chrome Extension Setup

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right corner)
3. Click "Load unpacked"
4. Select the `extension/` folder from this project
5. The extension should appear in your Chrome toolbar (puzzle piece icon)

**Extension Configuration:**
- Update `extension/popup.js` line 1 if backend is not on localhost:3000
- Current server URL: `http://localhost:3000`

### 3. Using Learn Hands On

1. Open any YouTube tutorial video
2. Click the extension icon in your Chrome toolbar
3. (Optional) Enter project context (e.g., "Learning Docker for DevOps")
4. Click "Go Hands On"
5. Wait for environment to build (~30-60 seconds depending on Dockerfile complexity)
6. Follow the interactive learning steps and execute commands in the terminal

---

## 📁 Project Structure

```
.
├── extension/                          # Chrome Extension (Manifest V3)
│   ├── manifest.json                  # Extension configuration
│   ├── popup.html                     # Extension popup UI
│   ├── popup.js                       # Extension logic & API calls
│   └── background.js                  # Service worker (minimal)
│
├── backend/                           # Python Flask Server
│   ├── app.py                         # Main application (857 lines)
│   │   ├── /health                    # Health check endpoint
│   │   ├── /api/generate-lab          # Step 1: Extract & summarize
│   │   ├── /api/start-lab             # Step 2: Generate Dockerfile
│   │   ├── /api/build-lab             # Step 3: Build & run
│   │   ├── /lab                       # Interactive lab UI
│   │   ├── /api/lab/<id>              # Get lab data & initial step
│   │   ├── /api/lab/<id>/execute      # Execute commands in container
│   │   └── /api/lab/<id>/ask          # AI Q&A support
│   │
│   ├── lab_manager.py                 # Lab session management
│   │   └── In-memory storage of active labs and learning state
│   │
│   ├── templates/
│   │   └── lab.html                   # Interactive terminal UI (678 lines)
│   │       ├── Video embedding
│   │       ├── Learning steps panel
│   │       ├── Terminal with command execution
│   │       └── Q&A panel
│   │
│   ├── requirements.txt                # Python dependencies
│   ├── .env.example                   # Environment variables template
│   ├── .env.local                     # Local environment (not committed)
│   ├── .venv/                         # Python virtual environment
│   └── README.md                      # Backend documentation
│
├── .gitignore                         # Git ignore rules
└── README.md                          # This file
```

---

## 🔐 Security & Best Practices

### ✅ Security Measures Implemented

1. **Input Validation**
   - All API endpoints validate request body and input sizes
   - YouTube URL format validation
   - Lab ID format validation
   - Maximum sizes enforced: transcripts (100KB), dockerfile (50KB), commands (4KB), questions (2KB)

2. **CORS Configuration**
   - Restricted to Chrome extension origins only
   - Prevents unauthorized access from other websites

3. **Secure Lab ID Generation**
   - Uses `secrets.token_hex()` for cryptographically secure random IDs
   - 16-character hex strings provide sufficient entropy

4. **OpenAI API Key Management**
   - Loaded from `.env.local` file (not committed to git)
   - Server validates key existence at startup
   - Key never exposed in error messages or responses

5. **XSS Protection**
   - All user input properly escaped in HTML templates
   - Uses `escapeHtml()` function for output encoding

6. **Error Handling**
   - Generic error messages to prevent information leakage
   - Detailed logs only in server console
   - No stack traces in API responses

### ⚠️ Important Notes

1. **Docker Permissions**
   - Application requires Docker daemon access
   - User must have Docker permissions (add to docker group or use sudo)
   - Containers run with default security

2. **Lab Isolation**
   - Labs are identified by secure random IDs
   - No user authentication (suitable for local/private use)
   - Anyone with lab_id can access that lab
   - Data stored in-memory (lost on server restart)

3. **Network Security**
   - Backend runs on localhost:3000 by default
   - Not suitable for multi-user/remote access in current configuration
   - For production: implement authentication, HTTPS, and persistent storage

4. **Resource Management**
   - Docker containers accumulate; manual cleanup recommended
   - In-memory storage limits concurrent labs based on available RAM
   - Command execution timeout: 30 seconds

---

## 🔧 Configuration

### Environment Variables (.env.local)

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Obtaining an API Key:**
1. Go to https://platform.openai.com/account/api-keys
2. Click "Create new secret key"
3. Copy the key and paste into `.env.local`
4. Restart the Flask server

### Customization Options

**Flask Debug Mode** (in `app.py` line ~856):
```python
app.run(host='localhost', port=3000, debug=True)
```
- Change `host` to `0.0.0.0` for remote access (use with caution)
- Change `port` if 3000 is already in use
- Set `debug=False` in production

**Command Timeout** (in `app.py` line ~749):
```python
timeout=30  # Command execution timeout in seconds
```

**Docker Build Timeout** (in `app.py` line ~117):
```python
timeout=300  # Docker build timeout in seconds (5 minutes)
```

---

## 🐛 Troubleshooting

### "Docker command not found"
```bash
# Ensure Docker is installed and running
docker --version

# Check if daemon is running
docker ps

# On macOS, start Docker Desktop if not running
open /Applications/Docker.app
```

### "OPENAI_API_KEY not set"
```bash
# Verify .env.local file exists and has the key
cat backend/.env.local

# Ensure key starts with 'sk-'
# Restart Flask server after updating
```

### "Lab environment still initializing..."
- Docker build can take 30-60 seconds depending on packages
- Watch Flask console for progress
- Check Docker logs: `docker logs lab-{lab_id}`

### "Command timed out (30 seconds)"
- Command took longer than 30 seconds
- Long-running operations (downloads, compilations) may need more time
- Modify timeout in `app.py` if needed

### "Invalid Ubuntu/Python package"
- Dockerfile generation may have suggested non-existent package
- Check Flask console for validation errors
- System retries up to 3 times automatically
- If still fails, verify package name exists on:
  - Ubuntu packages: https://packages.ubuntu.com/
  - Python packages: https://pypi.org/

---

## 📊 API Endpoints

### Lab Creation (3-Step Process)

**POST /api/generate-lab**
- Extracts transcript and generates summary
- Request: `{youtube_url, project_context?}`
- Response: `{success, labId, summary, transcript, ...}`

**POST /api/start-lab**
- Generates and validates Dockerfile
- Request: `{labId, transcript, project_context?}`
- Response: `{success, labId, dockerfile, issues?, warnings?}`

**POST /api/build-lab**
- Builds Docker image and starts container
- Request: `{labId, dockerfile, transcript?, project_context?, youtube_url?}`
- Response: `{success, labId, containerId, labUrl, ...}`

### Lab Interaction

**GET /api/lab/{lab_id}**
- Get lab data and generate initial learning step
- Response: `{lab_id, learning_plan, environment_description, video_id, ...}`

**POST /api/lab/{lab_id}/execute**
- Execute command in container
- Request: `{command}`
- Response: `{success, output, exit_code, next_step?}`

**POST /api/lab/{lab_id}/ask**
- Ask AI question about the tutorial
- Request: `{question}`
- Response: `{success, answer}`

**GET /health**
- Server health check
- Response: `{status: "ok"}`

---

## 🧪 Development

### Running Tests

Currently no automated tests. To add:
1. Create `tests/` directory
2. Add pytest test files
3. Run: `pytest tests/`

### Adding New Features

1. Update API endpoints in `app.py`
2. Add database models if persistence needed
3. Update `lab_manager.py` for state management
4. Update `lab.html` for UI changes
5. Update extension files for new workflows

### Code Structure

- **app.py**: Core Flask application and API logic
  - Main endpoints and workflows
  - Docker integration
  - OpenAI integration
  - Input validation

- **lab_manager.py**: Session state management
  - In-memory lab storage
  - Conversation history
  - Learning progress tracking

- **lab.html**: Interactive terminal UI
  - Video embedding
  - Command execution interface
  - Real-time output display
  - Q&A interface
  - XSS protection with escapeHtml()

- **extension/popup.js**: Extension orchestration
  - 3-step lab creation flow
  - Loading state management
  - API communication

---

## 📧 Support

For issues, feature requests, or questions:
- Check GitHub issues
- Review logs in Flask console
- Verify Docker is running
- Ensure OpenAI API key is valid

---

**Made with ❤️ for learners who learn by doing.**
