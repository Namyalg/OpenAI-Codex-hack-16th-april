// Background service worker
chrome.runtime.onInstalled.addListener(() => {
  console.log('Learn Hands On extension installed');
});

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'checkYouTube') {
    sendResponse({ isYouTube: isYouTubeVideo(sender.url) });
  }
});

function isYouTubeVideo(url) {
  return url.includes('youtube.com/watch') || url.includes('youtu.be/');
}
