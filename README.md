# 🚀 AI Browser Assistant (Chrome Extension + RAG + Multi-LLM)

## 📌 Overview

AI Browser Assistant is a **production-ready context-aware Chrome extension** that allows users to interact with any webpage using AI.

It extracts webpage content in real time and enables users to:

* ❓ Ask questions about the page
* 📝 Summarize content instantly
* 📚 Extract key insights and notes
* 📄 Generate structured document-style outputs

The system uses **Retrieval-Augmented Generation (RAG)** with **FAISS + HuggingFace embeddings**, and now supports **multi-LLM provider switching between Groq and Azure OpenAI** using a single `.env` variable.

---

## ✨ Features

* 🌐 Ask questions about any webpage
* 📝 Instant summarization
* 📌 Extract key points
* ⚡ Fast responses with Groq
* 🏢 Enterprise-ready Azure OpenAI support
* 🔄 Switch providers without code changes
* 🧠 Context-aware RAG pipeline
* 🧩 Clean FastAPI backend services
* 🛡️ Environment-based secure config

---

## 🏗️ Architecture

```text
Website → Chrome Extension → Backend (FastAPI)
        → Text Chunking → Embeddings → FAISS
        → Provider Router (Groq / Azure)
        → LLM Response → Extension UI
```

---

## 🛠️ Tech Stack

### Frontend (Chrome Extension)

* HTML
* CSS
* JavaScript

### Backend

* FastAPI
* Uvicorn
* Python Dotenv

### AI / ML

* Groq
* Azure OpenAI
* LangChain
* FAISS
* HuggingFace Sentence Transformers

---

## 📂 Project Structure

```bash
AI-Browser-Assistant/
│
├── extension/
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.js
│   └── content.js
│
├── backend/
│   ├── core/
│   │   └── config.py
│   ├── services/
│   │   ├── llm_service.py
│   │   └── task_service.py
│   └── main.py
│
├── .env
├── requirements.txt
└── README.md
```

---

## 🔑 Environment Setup

Create a `.env` file in the root directory:

```env
LLM_PROVIDER=groq

# Groq
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile

# Azure OpenAI
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_DEPLOYMENT_NAME=gpt-4o
```

### 🔄 Switch Providers

Use either:

```env
LLM_PROVIDER=groq
```

or

```env
LLM_PROVIDER=azure
```

No backend code changes required ✅

---

## 📦 Installation

### 1️⃣ Clone Repository

```bash
git clone https://github.com/rohitt08-l/AI-Browser-Assistant.git
cd AI-Browser-Assistant
```

### 2️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Run Backend

```bash
uvicorn backend.main:app --reload
```

Backend runs at:

```bash
http://127.0.0.1:8000
```

---

## 🧩 Load Chrome Extension

1. Open Chrome
2. Visit `chrome://extensions/`
3. Enable **Developer Mode**
4. Click **Load Unpacked**
5. Select the `extension/` folder

---

## 🚀 Usage

1. Open any website
2. Click the extension
3. Ask prompts like:

   * *What is this page about?*
   * *Summarize this page*
   * *Extract key points*
   * *Generate notes from this page*

---

## 🧠 Multi-LLM Design

All backend services call only:

```python
call_llm(prompt)
```

Internally it routes to:

* ⚡ **Groq** → ultra fast + low cost
* 🏢 **Azure OpenAI** → enterprise-grade deployment

This architecture is:

* scalable
* maintainable
* testable
* production-ready
* interview-friendly

---

## 🔮 Future Improvements

* 🔁 Automatic Groq → Azure fallback
* 🧠 Chat history + memory
* 🌐 Multi-page understanding
* 🎯 Highlight answers directly on webpage
* 📊 Advanced reranking retrieval
* 🧩 Browser-side caching
* 📱 Cross-browser support

---

## 🎯 Use Cases

* Research assistance
* Blog/article learning
* Fast summarization
* Competitive exam study support
* Developer documentation reading
* Productivity workflows

---

## 👨‍💻 Author

**Rohit Patil**

ML Engineer
