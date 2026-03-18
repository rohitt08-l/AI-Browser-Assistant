document.getElementById("askBtn").addEventListener("click", async () => {
  const question = document.getElementById("question").value;

  // Get active tab
  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  // Get page content
  chrome.tabs.sendMessage(tab.id, { action: "GET_PAGE_CONTENT" }, async (response) => {
    
    const pageContent = response.content;

    // Send to backend
    const res = await fetch("http://localhost:8000/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        question: question,
        page_content: pageContent
      })
    });

    const data = await res.json();

    document.getElementById("response").innerText = data.answer;
  });
});