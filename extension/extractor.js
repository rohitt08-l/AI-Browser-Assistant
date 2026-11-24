// Injected on demand (after lib/Readability.js) via chrome.scripting.executeScript.
// The value of the final expression is returned to the side panel.
(() => {
  const MAX_CHARS = 900000;
  const selection = (window.getSelection && window.getSelection().toString().trim()) || "";
  let content = "";
  let title = document.title || "";

  try {
    // Readability mutates the DOM it is given, so parse a clone.
    const article = new Readability(document.cloneNode(true), { charThreshold: 300 }).parse();
    if (article && article.textContent && article.textContent.trim().length > 200) {
      content = article.textContent;
      title = article.title || title;
    }
  } catch (e) {
    // Fall through to the plain-text fallback below.
  }

  if (!content) {
    // Not an article (app, search results, dashboard...): use visible text instead.
    content = (document.body && document.body.innerText) || "";
  }

  content = content.replace(/[ \t ]+/g, " ").replace(/\n\s*\n\s*/g, "\n\n").trim();

  return {
    title: title.slice(0, 500),
    url: location.href,
    content: content.slice(0, MAX_CHARS),
    selection: selection.slice(0, 20000),
  };
})();
