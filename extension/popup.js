document.getElementById("askBtn").addEventListener("click", async () => {
  const question = document.getElementById("question").value;
  const taskType = document.getElementById("taskType").value;

  const responseDiv = document.getElementById("response");

  if (!question) {
    responseDiv.innerText = "Please enter a question";
    return;
  }

  responseDiv.innerHTML = `<div class="loader">Thinking...</div>`;

  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  chrome.tabs.sendMessage(tab.id, { action: "GET_PAGE_CONTENT" }, async (response) => {

    try {
      const res = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          question: question,
          page_content: response.content,
          task_type: taskType
        })
      });

      const data = await res.json();

      responseDiv.innerText = data.answer;

    } catch (error) {
      responseDiv.innerText = "Error connecting to backend";
    }

  });
});


// COPY BUTTON
document.getElementById("copyBtn").addEventListener("click", () => {
  const text = document.getElementById("response").innerText;

  if (!text) return;

  navigator.clipboard.writeText(text);
  alert("Copied to clipboard!");
});