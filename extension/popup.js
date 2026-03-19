document.getElementById("askBtn").addEventListener("click", async () => {
  const question = document.getElementById("question").value;
  const taskType = document.getElementById("taskType").value;

  document.getElementById("response").innerText = "Loading...";

  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  chrome.tabs.sendMessage(tab.id, { action: "GET_PAGE_CONTENT" }, async (response) => {

    const pageContent = response.content;

    const res = await fetch("http://localhost:8000/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        question: question,
        page_content: pageContent,
        task_type: taskType
      })
    });

    const data = await res.json();

    document.getElementById("response").innerText = data.answer;
  });
});


// COPY BUTTON
document.getElementById("copyBtn").addEventListener("click", () => {
  const text = document.getElementById("response").innerText;
  navigator.clipboard.writeText(text);
  alert("Copied!");
});