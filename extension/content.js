// Extract page content
function getPageContent() {
  return document.body.innerText;
}

// Listen for message from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "GET_PAGE_CONTENT") {
    const content = getPageContent();
    sendResponse({ content: content });
  }
});