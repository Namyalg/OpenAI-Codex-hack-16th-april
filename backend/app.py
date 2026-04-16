#!/usr/bin/env python3
import os
import re
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import tempfile
import secrets
from lab_manager import create_lab, get_lab, update_lab_plan, add_conversation, add_executed_command
from werkzeug.exceptions import BadRequest

# Load environment variables from .env.local
def load_env():
    env_file = '.env.local'
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value

load_env()

app = Flask(__name__)
# CORS configuration - only allow requests from extension origins
CORS(app, resources={
    r"/api/*": {
        "origins": ["chrome-extension://*"],
        "methods": ["POST", "GET", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Initialize OpenAI client with proper validation
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("ERROR: OPENAI_API_KEY environment variable not set")
    print("Please set OPENAI_API_KEY in .env.local file")
    exit(1)

try:
    client = OpenAI(api_key=api_key)
    print("[Init] OpenAI API key loaded successfully")
except Exception as e:
    print(f"ERROR: Could not initialize OpenAI client: {e}")
    exit(1)

def extract_video_id(url):
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com\/v\/)([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def extract_transcript(video_id):
    """Extract transcript from YouTube video"""
    try:
        print(f"[Transcript] Extracting transcript for video: {video_id}")

        # Get transcript using YouTubeTranscriptApi instance method
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=['en'])

        # Extract text from transcript items (FetchedTranscriptSnippet objects)
        full_transcript = ' '.join([item.text for item in transcript])
        print(f"[Transcript] Successfully extracted {len(transcript)} entries")
        return full_transcript
    except Exception as e:
        raise Exception(f"Failed to extract transcript: {str(e)}")

def summarize_transcript(transcript):
    """Summarize transcript using OpenAI"""
    try:
        print("[Summary] Summarizing transcript...")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": f"Provide a concise 2-3 sentence summary of what this tutorial teaches. Focus on the main topics and learning outcomes:\n\n{transcript}"
                }
            ]
        )

        summary = response.choices[0].message.content
        print("[Summary] Summary generated successfully")
        return summary
    except Exception as e:
        raise Exception(f"Failed to summarize transcript: {str(e)}")


def build_and_run_lab(dockerfile_content, lab_id):
    """Build Docker image and run container"""
    try:
        # Create temp directory for Dockerfile
        temp_dir = tempfile.mkdtemp(prefix=f"lab_{lab_id}_")
        dockerfile_path = os.path.join(temp_dir, "Dockerfile")

        # Save Dockerfile
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)

        print(f"\n[Docker] Dockerfile saved to: {dockerfile_path}")

        # Build image
        image_name = f"lab-{lab_id}:{int(time.time())}"
        print(f"[Docker] Building image: {image_name}...")

        try:
            result = subprocess.run(
                ["docker", "build", "-t", image_name, temp_dir],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise Exception(f"Docker build failed: {error_msg}")

            print(f"[Docker] ✓ Image built successfully: {image_name}")
            print(result.stdout)

        except subprocess.TimeoutExpired:
            raise Exception("Docker build timeout (5 minutes exceeded)")
        except Exception as e:
            raise Exception(f"Docker build error: {str(e)}")

        # Run container
        print(f"[Docker] Starting container from {image_name}...")

        try:
            result = subprocess.run(
                [
                    "docker", "run",
                    "-d",
                    "--rm",
                    "-it",
                    "--name", f"lab-{lab_id}",
                    image_name,
                    "/bin/bash"
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise Exception(f"Docker run failed: {error_msg}")

            container_id = result.stdout.strip()
            print(f"[Docker] ✓ Container started: {container_id}")

            return {
                "success": True,
                "lab_id": lab_id,
                "image_name": image_name,
                "container_id": container_id,
                "dockerfile_path": dockerfile_path,
                "message": f"Lab environment ready! Container: {container_id[:12]}"
            }

        except subprocess.TimeoutExpired:
            raise Exception("Docker run timeout")
        except Exception as e:
            raise Exception(f"Docker run error: {str(e)}")

    except Exception as e:
        print(f"[Docker] Error: {str(e)}")
        raise


def is_valid_ubuntu_package(package_name, release="jammy"):
    """Check if a package exists in Ubuntu repositories"""
    try:
        print(f"    [Checking] Ubuntu package: {package_name}...", end=" ", flush=True)
        url = f"https://packages.ubuntu.com/search?keywords={package_name}&searchon=names&suite={release}&section=all"
        response = requests.get(url, timeout=5)
        is_valid = package_name in response.text
        print("✓" if is_valid else "✗")
        return is_valid
    except Exception as e:
        print(f"⚠ (timeout/error)")
        return None  # Unknown if can't check


def is_valid_python_package(package_name):
    """Check if a package exists on PyPI"""
    try:
        print(f"    [Checking] Python package: {package_name}...", end=" ", flush=True)
        # Remove version specifiers
        pkg_name = package_name.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].split('!=')[0]

        url = f"https://pypi.org/pypi/{pkg_name}/json"
        response = requests.get(url, timeout=5)
        is_valid = response.status_code == 200
        print("✓" if is_valid else "✗")
        return is_valid
    except Exception as e:
        print(f"⚠ (timeout/error)")
        return None  # Unknown if can't check


def validate_dockerfile(dockerfile_content):
    """Validate the generated Dockerfile against real package repositories"""
    issues = []
    warnings = []

    lines = dockerfile_content.split('\n')

    # Check for FROM statement
    has_from = any(line.strip().startswith('FROM') for line in lines)
    if not has_from:
        issues.append("Missing FROM statement (base image)")

    # Collect packages to validate
    apt_packages = []
    pip_packages = []

    for i, line in enumerate(lines, 1):
        line_lower = line.lower()

        # Extract apt packages
        if 'apt-get install' in line_lower or 'apt install' in line_lower:
            if 'apt-get install' in line_lower:
                packages_str = line.split('apt-get install')[1]
            else:
                packages_str = line.split('apt install')[1]

            # Parse packages (handling && and \\)
            packages_str = packages_str.replace('\\', ' ').replace('&&', ' ')
            pkg_list = [p.strip() for p in packages_str.split() if p.strip() and not p.startswith('-')]

            for pkg in pkg_list:
                if pkg and not pkg.startswith('-'):
                    apt_packages.append(pkg)

        # Extract pip packages
        if 'pip install' in line_lower:
            packages_str = line.split('pip install')[1]
            pkg_list = [p.strip() for p in packages_str.split() if p.strip() and not p.startswith('-')]

            for pkg in pkg_list:
                if pkg and not pkg.startswith('-'):
                    pip_packages.append(pkg)

        # Check for missing cleanup in apt installs
        if 'apt-get install' in line_lower and 'rm -rf /var/lib/apt/lists' not in dockerfile_content:
            warnings.append("apt-get install found but no cleanup of /var/lib/apt/lists - image may be larger")

    # Validate packages
    print("\n[Validation] Checking packages against repositories...")

    if apt_packages:
        print("[Validation] Ubuntu packages:")
        for pkg in apt_packages:
            result = is_valid_ubuntu_package(pkg)
            if result is False:
                issues.append(f"Invalid Ubuntu package: {pkg}")
            elif result is None:
                warnings.append(f"Could not verify Ubuntu package: {pkg}")

    if pip_packages:
        print("[Validation] Python packages:")
        for pkg in pip_packages:
            result = is_valid_python_package(pkg)
            if result is False:
                issues.append(f"Invalid Python package: {pkg}")
            elif result is None:
                warnings.append(f"Could not verify Python package: {pkg}")

    return issues, warnings


def generate_dockerfile_with_retry(transcript, project_context, max_retries=3):
    """Generate Dockerfile with retry logic - retries up to 3 times if validation fails"""
    attempt = 0
    best_dockerfile = None
    best_issues = []
    best_warnings = []

    while attempt < max_retries:
        attempt += 1
        print(f"\n[Dockerfile] Generation attempt {attempt}/{max_retries}...")

        dockerfile, issues, warnings = generate_dockerfile(
            transcript,
            project_context,
            previous_issues=best_issues if attempt > 1 else None
        )

        best_dockerfile = dockerfile
        best_issues = issues
        best_warnings = warnings

        # If no issues, we're done!
        if not issues:
            print(f"✓ Dockerfile validated successfully on attempt {attempt}")
            return dockerfile, issues, warnings

        # If there are issues and we haven't exhausted retries, retry
        if attempt < max_retries:
            print(f"\n⚠️  Attempt {attempt} had {len(issues)} validation issue(s). Retrying with feedback...")
            for issue in issues:
                print(f"  • {issue}")

    # After all retries, return the best attempt
    print(f"\n⚠️  After {max_retries} attempts, still have {len(best_issues)} validation issue(s)")
    return best_dockerfile, best_issues, best_warnings


def generate_dockerfile(transcript, project_context, previous_issues=None):
    """Generate a Dockerfile based on transcript and project context using OpenAI"""
    try:
        print("[Dockerfile] Generating Dockerfile...")

        # If this is a retry, add feedback about previous errors
        feedback_section = ""
        if previous_issues:
            feedback_section = f"""
PREVIOUS ATTEMPT VALIDATION ERRORS (FIX THESE):
{chr(10).join([f"- {issue}" for issue in previous_issues])}

IMPORTANT: Address all the above issues in this new attempt. Replace any invalid packages with valid alternatives.

"""

        prompt = f"""Based on the tutorial transcript and project context below, generate a suitable Dockerfile for a hands-on learning environment.

TUTORIAL TRANSCRIPT:
{transcript[:2000]}

PROJECT CONTEXT:
{project_context if project_context else 'No specific context provided - general learning setup'}

{feedback_section}
CRITICAL REQUIREMENTS - ONLY USE REAL, VALID PACKAGES:
1. Only use packages that ACTUALLY EXIST
2. For Python: only use real PyPI packages (numpy, pandas, requests, flask, django, etc.)
3. For system: only use real Ubuntu 22.04 packages (curl, git, build-essential, etc.)
4. For Node.js: only use real npm packages
5. Verify ALL package names are correct and commonly used
6. DO NOT invent, hallucinate, or make up package names
7. Do NOT use non-existent or typo'd package names

OTHER REQUIREMENTS:
8. Create a minimal, focused Dockerfile for learning
9. Include necessary tools and languages mentioned in the transcript
10. Set up a clean working environment
11. Use appropriate base image (ubuntu:22.04, python:3.11, node:18, etc.)
12. Install only absolutely necessary dependencies
13. For apt-get: always end with rm -rf /var/lib/apt/lists/*
14. Include comments explaining key sections
15. Make it suitable for interactive learning

VALID PACKAGE EXAMPLES:
- Python: numpy, pandas, requests, flask, django, matplotlib, pytest, beautifulsoup4
- System: curl, git, build-essential, python3-dev, nodejs, npm, wget, vim
- Node.js: express, axios, dotenv, jest, typescript, webpack

INVALID PACKAGES (DO NOT USE):
- Made-up names: pythonml, webpacker, djangoexpress
- Misspelled: numpyy, pandasss, requsts, flassk
- Fake versions or fake packages

Generate ONLY the Dockerfile content, no additional text or explanation."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_completion_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        dockerfile_content = response.choices[0].message.content

        # Validate the Dockerfile
        print("[Dockerfile] Validating Dockerfile...")
        issues, warnings = validate_dockerfile(dockerfile_content)

        print("\n" + "="*60)
        print("GENERATED DOCKERFILE:")
        print("="*60)
        print(dockerfile_content)
        print("="*60)

        if issues:
            print("\n❌ VALIDATION ISSUES (MUST FIX):")
            for issue in issues:
                print(f"  • {issue}")

        if warnings:
            print("\n⚠️  VALIDATION WARNINGS (REVIEW):")
            for warning in warnings:
                print(f"  • {warning}")

        if not issues and not warnings:
            print("\n✓ Dockerfile validation passed!")

        print("\n")

        return dockerfile_content, issues, warnings
    except Exception as e:
        raise Exception(f"Failed to generate Dockerfile: {str(e)}")


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/api/generate-lab', methods=['POST'])
def generate_lab():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    youtube_url = data.get('youtube_url')
    project_context = data.get('project_context', '')

    if not youtube_url:
        return jsonify({"error": "youtube_url is required"}), 400

    # Validate input sizes to prevent DoS
    if len(youtube_url) > 500:
        return jsonify({"error": "youtube_url is too long"}), 400

    if len(project_context) > 1000:
        return jsonify({"error": "project_context is too long (max 1000 chars)"}), 400

    print(f"[API] Received YouTube URL: {youtube_url}")
    if project_context:
        print(f"[API] Project context: {project_context}")

    try:
        # Extract video ID
        video_id = extract_video_id(youtube_url)
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL"}), 400

        # Extract transcript
        transcript = extract_transcript(video_id)

        # Summarize transcript
        summary = summarize_transcript(transcript)

        # Generate secure lab ID
        lab_id = f"lab_{secrets.token_hex(8)}"

        return jsonify({
            "success": True,
            "message": "Lab generation started",
            "youtube_url": youtube_url,
            "labId": lab_id,
            "summary": summary,
            "project_context": project_context,
            "transcript": transcript,
        }), 200

    except Exception as e:
        print(f"[API] Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/start-lab', methods=['POST'])
def start_lab():
    """Start a lab by generating a Dockerfile based on transcript and context"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    lab_id = data.get('labId')
    transcript = data.get('transcript')
    project_context = data.get('project_context', '')

    if not lab_id or not transcript:
        return jsonify({"error": "labId and transcript are required"}), 400

    # Validate lab_id format (should be lab_xxxxx)
    if not lab_id.startswith('lab_') or len(lab_id) < 10:
        return jsonify({"error": "Invalid lab_id format"}), 400

    # Validate transcript size (max 100KB)
    if len(transcript) > 102400:
        return jsonify({"error": "transcript is too large (max 100KB)"}), 400

    if len(project_context) > 1000:
        return jsonify({"error": "project_context is too long (max 1000 chars)"}), 400

    print(f"\n[StartLab] Starting lab: {lab_id}")
    print(f"[StartLab] Project context: {project_context if project_context else 'None'}")

    try:
        # Generate Dockerfile with retry logic (up to 3 attempts)
        dockerfile, issues, warnings = generate_dockerfile_with_retry(transcript, project_context, max_retries=3)

        # Return error if there are still validation issues after all retries
        if issues:
            return jsonify({
                "success": False,
                "message": f"Dockerfile has {len(issues)} validation issue(s) after 3 attempts",
                "labId": lab_id,
                "dockerfile": dockerfile,
                "issues": issues,
                "warnings": warnings,
            }), 400

        return jsonify({
            "success": True,
            "message": "Lab environment created successfully after validation",
            "labId": lab_id,
            "dockerfile": dockerfile,
            "issues": issues,
            "warnings": warnings,
        }), 200

    except Exception as e:
        print(f"[StartLab] Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/build-lab', methods=['POST'])
def build_lab():
    """Build Docker image and start container"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    lab_id = data.get('labId')
    dockerfile = data.get('dockerfile')
    transcript = data.get('transcript', '')
    project_context = data.get('project_context', '')
    youtube_url = data.get('youtube_url', '')

    if not lab_id or not dockerfile:
        return jsonify({"error": "labId and dockerfile are required"}), 400

    # Validate lab_id format
    if not lab_id.startswith('lab_') or len(lab_id) < 10:
        return jsonify({"error": "Invalid lab_id format"}), 400

    # Validate dockerfile size (max 50KB)
    if len(dockerfile) > 51200:
        return jsonify({"error": "dockerfile is too large (max 50KB)"}), 400

    print(f"\n[BuildLab] Building lab environment: {lab_id}")

    try:
        # Extract video ID from URL
        video_id = None
        if youtube_url:
            video_id = extract_video_id(youtube_url)

        # Build and run the lab
        result = build_and_run_lab(dockerfile, lab_id)

        # Create lab session and store container info
        create_lab(lab_id, transcript, project_context, result["container_id"], dockerfile, video_id)

        return jsonify({
            "success": True,
            "message": result["message"],
            "labId": lab_id,
            "imageName": result["image_name"],
            "containerId": result["container_id"],
            "dockerfilePath": result["dockerfile_path"],
            "labUrl": f"/lab?lab={lab_id}"
        }), 200

    except Exception as e:
        print(f"[BuildLab] Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/lab', methods=['GET'])
def lab_page():
    """Serve the lab terminal interface"""
    return render_template('lab.html')


def parse_environment_setup(dockerfile, transcript, project_context):
    """Parse dockerfile and transcript to generate environment description"""
    try:
        print("[EnvSetup] Generating environment description...")

        # Extract key info from dockerfile
        lines = dockerfile.split('\n')
        base_image = None
        packages = []

        for line in lines:
            if 'FROM' in line:
                base_image = line.replace('FROM', '').strip()
            if 'apt-get install' in line or 'apt install' in line:
                # Extract packages
                if 'apt-get install' in line:
                    pkg_str = line.split('apt-get install')[1]
                else:
                    pkg_str = line.split('apt install')[1]
                pkg_str = pkg_str.replace('\\', ' ').replace('&&', ' ')
                pkgs = [p.strip() for p in pkg_str.split() if p.strip() and not p.startswith('-')]
                packages.extend(pkgs[:5])  # First 5 packages

        # Generate description using AI
        prompt = f"""Based on the tutorial and the environment setup below, write a SHORT 2-line description of what this learning environment provides.

TUTORIAL TOPIC:
{transcript[:500]}

BASE IMAGE: {base_image or 'standard'}
KEY PACKAGES: {', '.join(packages) if packages else 'standard tools'}

Write EXACTLY 2 lines explaining:
Line 1: What this environment is built on (base image + main purpose)
Line 2: What tools/packages are included and why they matter for learning this tutorial

Keep each line under 80 characters. Be concise and educational."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_completion_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        description = response.choices[0].message.content
        print(f"[EnvSetup] ✓ Environment description generated")
        return description

    except Exception as e:
        print(f"[EnvSetup] Error generating description: {str(e)}")
        # Fallback
        base = base_image or "Linux"
        pkgs = ", ".join(packages[:3]) if packages else "development tools"
        return f"Environment: {base}\nIncludes: {pkgs} and other essential packages for hands-on learning."


@app.route('/api/lab/<lab_id>', methods=['GET'])
def get_lab_data(lab_id):
    """Get lab data and generate initial learning step"""
    lab = get_lab(lab_id)

    if not lab:
        return jsonify({"error": "Lab not found"}), 404

    # Generate environment setup description
    environment_description = parse_environment_setup(lab.dockerfile, lab.transcript, lab.project_context)

    # Generate initial step if not already done
    if not lab.learning_plan:
        try:
            print(f"[LearningPlan] Generating initial step for lab {lab_id}...")

            prompt = f"""Based on this tutorial, generate ONLY the first learning step to get started. Be specific and actionable.

TUTORIAL CONTENT:
{lab.transcript[:1500]}

LEARNER'S CONTEXT:
{lab.project_context if lab.project_context else 'General hands-on learning'}

Generate ONLY ONE step in this exact format:

**Step Title**: Brief explanation of why this is the first step and what they'll learn.
`command to try`

Keep it short, clear, and actionable. This is just the starting point - more steps will be generated dynamically based on what they do."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_completion_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )

            learning_plan = response.choices[0].message.content
            update_lab_plan(lab_id, learning_plan)
            lab.learning_plan = learning_plan
            print(f"[LearningPlan] ✓ Initial step generated for {lab_id}")

        except Exception as e:
            print(f"[LearningPlan] Error generating initial step: {str(e)}")
            lab.learning_plan = "**Explore Your Environment**: See what's available in the container.\n`ls -la`"

    return jsonify({
        "lab_id": lab_id,
        "project_context": lab.project_context,
        "learning_plan": lab.learning_plan,
        "environment_description": environment_description,
        "video_id": lab.video_id,
    }), 200


def generate_next_step(lab_id, last_command, last_output):
    """Generate the next learning step based on what the user just did"""
    lab = get_lab(lab_id)
    if not lab:
        return None

    try:
        print(f"[NextStep] Generating next step for lab {lab_id}...")

        # Build context of what they've done
        executed_summary = "\n".join([
            f"- Ran: {cmd['command']}\n  Output: {cmd['output'][:200]}..."
            for cmd in lab.executed_commands[-3:]  # Last 3 commands
        ])

        prompt = f"""Based on what the learner just did, generate the NEXT best learning step.

TUTORIAL CONTENT:
{lab.transcript[:1500]}

LEARNER'S CONTEXT:
{lab.project_context if lab.project_context else 'General hands-on learning'}

WHAT THEY JUST DID:
Command: {last_command}
Output:
{last_output[:500]}

THEIR EXPLORATION SO FAR:
{executed_summary if executed_summary else 'Just getting started'}

Based on what they learned from that last output, what should they explore or learn NEXT? Generate ONE practical next step that builds on what they just did.

Format (replace TITLE and COMMAND with actual values):
**TITLE**: Why this is the logical next step given their recent action. Keep it brief and actionable.
`COMMAND`

Examples:
**Explore the filesystem**: Now that you see what's available, look deeper into the directory structure.
`find . -type f -name "*.py" | head -10`

**Test the setup**: Verify everything is working correctly.
`python3 --version && git --version`

Be adaptive - if they're exploring successfully, guide them deeper. If they hit an error, help them debug. Make each step flow naturally from the previous one."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_completion_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        next_step = response.choices[0].message.content
        print(f"[NextStep] ✓ Generated next step for {lab_id}")
        return next_step

    except Exception as e:
        print(f"[NextStep] Error generating next step: {str(e)}")
        return None


@app.route('/api/lab/<lab_id>/execute', methods=['POST'])
def execute_command(lab_id):
    """Execute a command in the lab container and generate next step"""
    lab = get_lab(lab_id)

    if not lab:
        return jsonify({"error": "Lab not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    command = data.get('command', '').strip()

    if not command:
        return jsonify({"error": "Command required"}), 400

    # Validate command size to prevent abuse
    if len(command) > 4096:
        return jsonify({"error": "Command is too long (max 4096 chars)"}), 400

    if not lab.container_id:
        return jsonify({"error": "Lab container not available"}), 400

    print(f"[Execute] Running command in {lab_id}: {command}")

    try:
        # Execute command in container
        result = subprocess.run(
            ["docker", "exec", lab.container_id, "sh", "-c", command],
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout
        if result.returncode != 0:
            error_output = result.stderr or result.stdout
            output = f"[Exit code: {result.returncode}] {error_output}"

        # Store executed command
        add_executed_command(lab_id, command, output)

        # Generate next step based on this command's output
        next_step = generate_next_step(lab_id, command, output)

        return jsonify({
            "success": True,
            "command": command,
            "output": output,
            "exit_code": result.returncode,
            "next_step": next_step
        }), 200

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Command timeout (30 seconds)"}), 500
    except Exception as e:
        print(f"[Execute] Error: {str(e)}")
        return jsonify({"error": f"Execution error: {str(e)}"}), 500


@app.route('/api/lab/<lab_id>/ask', methods=['POST'])
def ask_question(lab_id):
    """Handle user question and update learning plan"""
    lab = get_lab(lab_id)

    if not lab:
        return jsonify({"error": "Lab not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    question = data.get('question', '').strip()

    if not question:
        return jsonify({"error": "Question required"}), 400

    # Validate question size
    if len(question) > 2000:
        return jsonify({"error": "Question is too long (max 2000 chars)"}), 400

    print(f"[Ask] Question for {lab_id}: {question}")

    # Add question to conversation history
    add_conversation(lab_id, 'user', question)

    try:
        # Build context for AI response
        executed_commands_summary = ""
        if lab.executed_commands:
            executed_commands_summary = "\n".join([
                f"- Ran: {cmd['command']}"
                for cmd in lab.executed_commands[-5:]  # Last 5 commands
            ])

        prompt = f"""You are helping someone learn from a tutorial. Answer their question concisely based on the tutorial context.

TUTORIAL CONTEXT:
{lab.transcript[:1000]}

PROJECT CONTEXT:
{lab.project_context if lab.project_context else 'General learning'}

WHAT THEY'VE DONE SO FAR:
{executed_commands_summary if executed_commands_summary else 'Just started exploring the environment'}

THEIR QUESTION:
{question}

Provide a helpful, concise answer (1-2 sentences). Focus on practical guidance."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        answer = response.choices[0].message.content
        add_conversation(lab_id, 'assistant', answer)

        # Optionally update learning plan based on their question
        should_update_plan = any(word in question.lower() for word in ['how', 'what', 'next', 'after', 'then'])

        if should_update_plan and len(lab.executed_commands) > 3:
            updated_plan = lab.learning_plan
            # In a real scenario, we'd regenerate the plan here
        else:
            updated_plan = None

        return jsonify({
            "success": True,
            "question": question,
            "answer": answer,
            "updated_plan": updated_plan
        }), 200

    except Exception as e:
        print(f"[Ask] Error: {str(e)}")
        return jsonify({"error": f"Failed to process question: {str(e)}"}), 500


if __name__ == '__main__':
    print("[Init] Starting server...")
    print(f"[Init] OpenAI API Key: {'Set' if os.getenv('OPENAI_API_KEY') else 'Not Set'}")
    print("[Init] Debug mode enabled - server will auto-reload on file changes")
    app.run(host='localhost', port=3000, debug=True)
