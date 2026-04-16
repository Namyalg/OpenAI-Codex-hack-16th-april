const SERVER_URL = 'http://localhost:3000';

document.addEventListener('DOMContentLoaded', () => {
  const handsOnButton = document.getElementById('handsOnButton');

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentTab = tabs[0];
    if (!isYouTubeVideo(currentTab.url)) {
      handsOnButton.disabled = true;
    }
  });

  handsOnButton.addEventListener('click', handleGoHandsOn);
});

function isYouTubeVideo(url) {
  return url.includes('youtube.com/watch') || url.includes('youtu.be/');
}

async function updateLoadingMessage(message) {
  const loadingText = document.getElementById('loadingText');
  if (loadingText) {
    loadingText.textContent = message;
  }
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

async function handleGoHandsOn() {
  const errorDiv = document.getElementById('error');
  const successDiv = document.getElementById('success');
  const loadingDiv = document.getElementById('loading');
  const handsOnButton = document.getElementById('handsOnButton');

  errorDiv.style.display = 'none';
  successDiv.style.display = 'none';

  chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
    const currentTab = tabs[0];
    const youtubeUrl = currentTab.url;

    if (!isYouTubeVideo(youtubeUrl)) {
      showError('Not a YouTube video');
      return;
    }

    handsOnButton.disabled = true;
    loadingDiv.style.display = 'flex';

    const projectContext = document.getElementById('projectContext').value.trim();

    try {
      // Step 1: Generate lab (extract transcript + summarize)
      await updateLoadingMessage('👀 Understanding the video...');
      let response = await fetch(`${SERVER_URL}/api/generate-lab`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          youtube_url: youtubeUrl,
          project_context: projectContext
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Error: ${response.status}`);
      }

      const labData = await response.json();
      const labId = labData.labId;
      const transcript = labData.transcript;

      // Step 2: Generate dockerfile
      await updateLoadingMessage('🧠 Understanding your project...');
      response = await fetch(`${SERVER_URL}/api/start-lab`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          labId: labId,
          transcript: transcript,
          project_context: projectContext
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Error: ${response.status}`);
      }

      const dockerfileData = await response.json();
      const dockerfile = dockerfileData.dockerfile;

      // Step 3: Build and run
      await updateLoadingMessage('🚀 Spinning up your environment...');
      response = await fetch(`${SERVER_URL}/api/build-lab`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          labId: labId,
          dockerfile: dockerfile,
          transcript: transcript,
          project_context: projectContext,
          youtube_url: youtubeUrl,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Error: ${response.status}`);
      }

      const buildData = await response.json();

      // Success!
      await updateLoadingMessage('✨ Let\'s go hands on...');
      showSuccess(`🎉 You're all set!\n\nReady to learn?`);

      // Open lab in new tab after 1 second
      setTimeout(() => {
        const labUrl = `${SERVER_URL}/lab?lab=${buildData.labId}`;
        chrome.tabs.create({ url: labUrl });
      }, 1000);

    } catch (error) {
      showError(`Error: ${error.message}`);
      console.error('Error:', error);
    } finally {
      handsOnButton.disabled = false;
      loadingDiv.style.display = 'none';
    }
  });
}
