# 🤖 Chatbase Clone — Complete Setup Guide

A full Chatbase.co replica with website-only data source. Three components: **Colab Crawler**, **HuggingFace Backend**, and **Static Frontend**.

---

## 📁 Project Structure

```
new project/
├── colab/
│   └── crawler.py          ← Copy-paste into Google Colab
├── backend/
│   ├── app.py              ← FastAPI backend
│   ├── requirements.txt    ← Python dependencies
│   ├── Dockerfile          ← For HuggingFace Spaces
│   └── README.md           ← HF Spaces metadata
└── frontend/
    ├── index.html           ← Landing page
    ├── dashboard.html       ← Dashboard
    ├── create.html          ← Create chatbot form
    ├── chat.html            ← Chat interface
    ├── embed.html           ← Settings & embed code
    ├── style.css            ← Design system
    ├── app.js               ← Shared utilities
    └── widget.js            ← Embeddable chat widget
```

---

## Step 1: Get a Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **"Create API Key"**
3. Copy the key — you'll need it in Step 3

---

## Step 2: Crawl Your Website (Google Colab)

1. Open [Google Colab](https://colab.research.google.com/)
2. Create a new notebook
3. Copy-paste the contents of `colab/crawler.py` into cells:

**Cell 1 — Install dependencies:**
```python
!pip install requests beautifulsoup4 lxml tqdm
```

**Cell 2 — Configure:**
```python
CONFIG = {
    "start_url": "https://YOUR-WEBSITE.com",  # ← Change this
    "max_pages": 100,
    "max_depth": 3,
    "crawl_delay": 1.0,
    "chatbot_name": "my-chatbot",
    "output_dir": "/content/crawl_output",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "user_agent": "Mozilla/5.0 ...",
    "backend_url": "https://YOUR-SPACE.hf.space",  # ← Change after Step 3
}
```

**Cells 3–5** — Copy remaining code sections from `crawler.py`

4. Run all cells
5. Download `chunks.json` from `/content/crawl_output/`

---

## Step 3: Deploy Backend to HuggingFace Spaces

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Settings:
   - **Space name**: `chatbase-api` (or any name)
   - **SDK**: Select **Docker**
   - **Visibility**: Public (or Private)
3. Click **Create Space**
4. Upload these files from the `backend/` folder:
   - `app.py`
   - `requirements.txt`
   - `Dockerfile`
   - `README.md`
5. Go to **Settings** → **Variables and secrets**
   - Add secret: `GEMINI_API_KEY` = your key from Step 1
6. The space will build and deploy automatically
7. Your API URL will be: `https://YOUR-USERNAME-chatbase-api.hf.space`

### Test the API:
```
curl https://YOUR-SPACE.hf.space/api/health
```

---

## Step 4: Upload Crawled Data

**Option A: From Colab** (uncomment the last cell in crawler.py):
```python
CONFIG["backend_url"] = "https://YOUR-SPACE.hf.space"
upload_result = upload_to_backend(chunks_data, CONFIG)
```

**Option B: Using curl:**
```bash
curl -X POST https://YOUR-SPACE.hf.space/api/chatbot \
  -H "Content-Type: application/json" \
  -d @chunks.json
```

**Option C: From the Frontend UI:**
1. Open `create.html`
2. Upload `chunks.json` file
3. Click "Create Chatbot"

---

## Step 5: Host the Frontend

### Option A: GitHub Pages (Free)
1. Create a GitHub repo
2. Upload all files from `frontend/` to the repo
3. Go to **Settings** → **Pages** → **Source: main branch**
4. Your site will be at: `https://username.github.io/repo-name/`

### Option B: Netlify (Free)
1. Go to [netlify.com](https://netlify.com)
2. Drag-drop the `frontend/` folder
3. Done! You get a URL like `https://random-name.netlify.app`

### Option C: Vercel (Free)
1. Go to [vercel.com](https://vercel.com)
2. Import your GitHub repo or upload files
3. Deploy

### Option D: Open Locally
Just open `frontend/index.html` in your browser.

---

## Step 6: Configure the Frontend

1. Open the Dashboard page
2. Click **🔑 API Settings** in the sidebar
3. Enter your HuggingFace Space URL: `https://YOUR-SPACE.hf.space`
4. Click **Save & Connect**
5. If green dot appears → you're connected!

---

## Step 7: Embed on Your Website

1. Go to **Settings & Embed** page
2. Copy the embed script code:

```html
<script>
  window.chatbaseConfig = {
    chatbotId: "my-chatbot",
    apiUrl: "https://YOUR-SPACE.hf.space",
    themeColor: "#6C63FF",
  };
</script>
<script src="https://YOUR-FRONTEND-URL/widget.js" defer></script>
```

3. Paste it into your website's HTML before `</body>`

---

## API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/chatbot` | Create chatbot (send chunks.json) |
| `GET` | `/api/chatbots` | List all chatbots |
| `GET` | `/api/chatbot/{id}` | Get chatbot info |
| `PUT` | `/api/chatbot/{id}/settings` | Update settings |
| `DELETE` | `/api/chatbot/{id}` | Delete chatbot |
| `POST` | `/api/chat/{id}` | Send message & get response |

### Chat Request Body:
```json
{
  "message": "What is your pricing?",
  "history": [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello! How can I help?"}
  ],
  "stream": false
}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API: Not Connected | Check your HF Space URL in API Settings |
| "Gemini API key not configured" | Add `GEMINI_API_KEY` secret in HF Space settings |
| Crawler stuck / blocked | Increase `crawl_delay`, reduce `max_pages` |
| "No chunks provided" | Make sure `chunks.json` has a `chunks` array |
| Widget not showing | Check browser console for errors; verify `apiUrl` |
| HF Space won't build | Check `Dockerfile` and `requirements.txt` are uploaded |

---

## Free Tier Limits

| Service | Free Tier |
|---------|-----------|
| **Google AI Studio** | 15 RPM, 1M TPM, 1500 RPD for Gemini 1.5 Flash |
| **HuggingFace Spaces** | 2 vCPU, 16GB RAM (Docker), limited uptime |
| **GitHub Pages** | 100GB bandwidth/month |
| **Netlify** | 100GB bandwidth/month |
