# AI Browser Assistant (Chrome Extension + RAG + Groq)

## Overview

AI Browser Assistant is a **context-aware Chrome extension** that allows users to interact with any webpage using AI.

It extracts webpage content in real-time and enables users to:

* Ask questions about the page
* Summarize content
* Extract key insights

The system uses **Retrieval-Augmented Generation (RAG)** with **Groq LLM** for fast and accurate responses.

---

## Features

* Ask questions about any webpage
* Summarize content instantly
* Extract key points
* Fast responses using Groq LLM
* Works on any website
* Context-aware answers (RAG-based)

---

## Architecture

```text
Website → Chrome Extension → Backend (FastAPI)
        → Text Processing → Embeddings → FAISS
        → Groq LLM → Response → Extension UI
```

---

## Tech Stack

### Frontend (Chrome Extension)

* HTML
* CSS
* JavaScript

### Backend

* FastAPI
* Uvicorn

### AI/ML

* Groq LLM (LLaMA 3.1)
* LangChain
* FAISS (Vector Database)
* HuggingFace Embeddings

---

## 📂 Project Structure

```
ai-browser-assistant/
│
├── extension/
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.js
│   ├── content.js
│
├── backend/
│   ├── app.py
│
├── .env
├── requirements.txt
└── README.md
```

---

## 🔑 Environment Setup

Create a `.env` file in the root directory:

```
GROQ_API_KEY=your_api_key_here
```

---

## 📦 Installation

### 1. Clone Repository

```
git clone https://github.com/rohitt08-l/AI-Browser-Assistant.git
cd ai-browser-assistant
```

### 2. Install Dependencies

```
pip install -r requirements.txt
```

---

## ▶️ Run Backend

```
uvicorn backend.app:app --reload
```

---

## Load Chrome Extension

1. Open Chrome
2. Go to: `chrome://extensions/`
3. Enable **Developer Mode**
4. Click **Load Unpacked**
5. Select the `extension/` folder

---

## Usage

1. Open any website
2. Click the extension
3. Ask questions like:

   * "What is this page about?"
   * "Summarize this page"
   * "Give key points"

---

## Future Improvements

* 🔄 Caching for faster responses
* 🧠 Chat history support
* 🌐 Multi-page memory
* 🎯 Highlight answers on webpage
* 📊 Advanced retrieval (reranking)

---

## 🧠 Key Concepts Used

* Retrieval-Augmented Generation (RAG)
* Vector Embeddings
* Semantic Search
* LLM-based Question Answering

---

## 🎯 Use Cases

* Research assistance
* Learning from blogs/articles
* Quick summarization
* Productivity enhancement

---

## 🧑‍💻 Author

Rohit Patil
Machine Learning Engineer

---

