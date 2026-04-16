const SERVER_URL = 'http://localhost:3000';
let currentLabData = null;
let dockerfileGenerated = null;

document.addEventListener('DOMContentLoaded', () => {
  const learnButton = document.getElementById('learnButton');
  const startLabButton = document.getElementById('startLabButton');
  const buildLabButton = document.getElementById('buildLabButton');

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentTab = tabs[0];
    if (!isYouTubeVideo(currentTab.url)) {
      learnButton.disabled = true;
    }
  });

  learnButton.addEventListener('click', handleLearn);
  startLabButton.addEventListener('click', handleStartLab);
  buildLabButton.addEventListener('click', handleBuildLab);
});

function isYouTubeVideo(url) {
  return url.includes('youtube.com/watch') || url.includes('youtu.be/');
}

async function handleLearn() {
  const errorDiv = document.getElementById('error');
  const successDiv = document.getElementById('success');
  const loadingDiv = document.getElementById('loading');
  const learnButton = document.getElementById('learnButton');

  errorDiv.style.display = 'none';
  successDiv.style.display = 'none';

  chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
    const currentTab = tabs[0];
    const youtubeUrl = currentTab.url;

    if (!isYouTubeVideo(youtubeUrl)) {
      showError('Not a YouTube video');
      return;
    }

    learnButton.disabled = true;
    loadingDiv.style.display = 'flex';

    const projectContext = document.getElementById('projectContext').value.trim();

    try {
      const response = await fetch(`${SERVER_URL}/api/generate-lab`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          youtube_url: youtubeUrl,
          project_context: projectContext
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Error: ${response.status}`);
      }

      const data = await response.json();

      // Store lab data for "Start Lab" button
      currentLabData = data;

      const message = data.summary ? `📚 ${data.summary}` : `Ready! Lab ID: ${data.labId}`;
      showSuccess(message);

      // Show "Start Lab" button
      document.getElementById('startLabButton').style.display = 'block';
    } catch (error) {
      showError(`Error: ${error.message}`);
      console.error('Error:', error);
    } finally {
      learnButton.disabled = false;
      loadingDiv.style.display = 'none';
    }
  });
}

function showError(message) {
  const errorDiv = document.getElementById('error');
  errorDiv.textContent = message;
  errorDiv.style.display = 'block';
}

function showSuccess(message) {
  const successDiv = document.getElementById('success');
  successDiv.textContent = message;
  successDiv.style.display = 'block';
}

async function handleStartLab() {
  if (!currentLabData || !currentLabData.transcript) {
    showError('No transcript data available');
    return;
  }

  const errorDiv = document.getElementById('error');
  const loadingDiv = document.getElementById('loading');
  const startLabButton = document.getElementById('startLabButton');

  errorDiv.style.display = 'none';
  startLabButton.disabled = true;
  loadingDiv.style.display = 'flex';

  try {
    const response = await fetch(`${SERVER_URL}/api/start-lab`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        labId: currentLabData.labId,
        transcript: currentLabData.transcript,
        project_context: currentLabData.project_context
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `Error: ${response.status}`);
    }

    const data = await response.json();

    // Store dockerfile for build step
    dockerfileGenerated = data.dockerfile;

    if (data.success) {
      showSuccess('✓ Dockerfile validation passed!');
      document.getElementById('buildLabButton').style.display = 'block';
    } else if (data.issues && data.issues.length > 0) {
      showError(`⚠️ After 3 attempts, ${data.issues.length} validation issue(s) remain.`);
      // Still allow build even with warnings - user can review logs
      dockerfileGenerated = data.dockerfile;
      document.getElementById('buildLabButton').style.display = 'block';
    } else {
      showSuccess('Dockerfile generated!');
      document.getElementById('buildLabButton').style.display = 'block';
    }
  } catch (error) {
    showError(`Error: ${error.message}`);
    console.error('Error:', error);
  } finally {
    startLabButton.disabled = false;
    loadingDiv.style.display = 'none';
  }
}

async function handleBuildLab() {
  if (!currentLabData || !dockerfileGenerated) {
    showError('Generate Dockerfile first');
    return;
  }

  const errorDiv = document.getElementById('error');
  const loadingDiv = document.getElementById('loading');
  const buildLabButton = document.getElementById('buildLabButton');

  errorDiv.style.display = 'none';
  buildLabButton.disabled = true;
  loadingDiv.style.display = 'flex';
  loadingDiv.querySelector('span').textContent = 'Building Docker image...';

  try {
    const response = await fetch(`${SERVER_URL}/api/build-lab`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        labId: currentLabData.labId,
        dockerfile: dockerfileGenerated,
        transcript: currentLabData.transcript,
        project_context: currentLabData.project_context,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `Error: ${response.status}`);
    }

    const data = await response.json();
    showSuccess(`🐳 ${data.message}\n\nContainer ID: ${data.containerId.substring(0, 12)}`);

    // Open lab terminal in new tab after 1 second
    setTimeout(() => {
      const labUrl = `${SERVER_URL}/lab?lab=${data.labId}`;
      chrome.tabs.create({ url: labUrl });
    }, 1000);
  } catch (error) {
    showError(`Build error: ${error.message}`);
    console.error('Error:', error);
  } finally {
    buildLabButton.disabled = false;
    loadingDiv.style.display = 'none';
  }
}
