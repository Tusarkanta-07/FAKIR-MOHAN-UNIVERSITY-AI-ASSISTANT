# =============================================================================
# 🎓 FMU AI ASSISTANT — BACKEND API
# =============================================================================
# Deploy to Hugging Face Spaces (Docker SDK)
# RAG-powered chat using FAISS + Gemini + OpenRouter fallback
# =============================================================================

import os
import json
import hashlib
import time
import shutil
import httpx
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np
import faiss
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
import google.generativeai as genai

# =============================================================================
# Configuration
# =============================================================================

DATA_DIR = os.environ.get("DATA_DIR", "/data")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 5  # Number of chunks to retrieve

# Gemini fallback chain
GEMINI_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemini-3.1-flash-live-preview"
]

# OpenRouter free models (used after Gemini exhausted)
OPENROUTER_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "meta-llama/llama-4-maverick:free",
    "qwen/qwen3-235b-a22b:free",
]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# =============================================================================
# Initialize
# =============================================================================

app = FastAPI(
    title="FMU AI Assistant API",
    description="RAG-powered chatbot backend using FAISS + Gemini + OpenRouter",
    version="2.0.0",
)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load embedding model at startup
print("Loading embedding model...")
embed_model = SentenceTransformer(EMBED_MODEL_NAME)
EMBED_DIM = embed_model.get_sentence_embedding_dimension()

# Configure Gemini models
gemini_models = []
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    for model_name in GEMINI_MODELS:
        try:
            gemini_models.append({
                'name': model_name,
                'provider': 'gemini',
                'model': genai.GenerativeModel(model_name),
            })
            print(f"  ✅ Gemini: {model_name}")
        except Exception as e:
            print(f"  ⚠️ Gemini failed: {model_name}: {e}")
else:
    print("⚠️  GEMINI_API_KEY not set.")

# Configure OpenRouter models
openrouter_models = []
if OPENROUTER_API_KEY:
    for model_name in OPENROUTER_MODELS:
        openrouter_models.append({
            'name': model_name,
            'provider': 'openrouter',
        })
        print(f"  ✅ OpenRouter: {model_name}")
else:
    print("ℹ️  OPENROUTER_API_KEY not set (optional fallback).")

# Unified fallback chain: Gemini first, then OpenRouter
all_models = gemini_models + openrouter_models
print(f"\n📦 Total models in fallback chain: {len(all_models)}")
if not all_models:
    print("⚠️  No LLM models configured! Set GEMINI_API_KEY and/or OPENROUTER_API_KEY.")

# In-memory store for chatbot data
chatbots: Dict[str, Dict[str, Any]] = {}

# =============================================================================
# Pydantic Models
# =============================================================================

class ChunkData(BaseModel):
    chunk_id: int
    source_url: str = ""
    page_title: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    content: str

class CreateChatbotRequest(BaseModel):
    chatbot_id: str
    source_url: str = ""
    total_chunks: int = 0
    chunk_config: dict = {}
    chunks: List[ChunkData]

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    stream: bool = False

class ChatbotSettings(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    initial_message: Optional[str] = None
    theme_color: Optional[str] = None

# =============================================================================
# Helper Functions
# =============================================================================

def get_chatbot_dir(chatbot_id: str) -> Path:
    """Get the directory for a specific chatbot's data."""
    safe_id = hashlib.md5(chatbot_id.encode()).hexdigest()[:12]
    return Path(DATA_DIR) / f"chatbot_{safe_id}"

def build_faiss_index(chunks: List[ChunkData]) -> tuple:
    """Build a FAISS index from text chunks."""
    texts = [c.content for c in chunks]
    print(f"  Embedding {len(texts)} chunks...")
    embeddings = embed_model.encode(texts, show_progress_bar=True, batch_size=32)
    embeddings = np.array(embeddings, dtype='float32')

    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings)

    # Create index
    index = faiss.IndexFlatIP(EMBED_DIM)  # Inner product = cosine on normalized
    index.add(embeddings)

    return index, texts

def search_chunks(chatbot_id: str, query: str, top_k: int = TOP_K) -> List[Dict]:
    """Search for relevant chunks using FAISS."""
    bot = chatbots.get(chatbot_id)
    if not bot:
        return []

    query_embedding = embed_model.encode([query])
    query_embedding = np.array(query_embedding, dtype='float32')
    faiss.normalize_L2(query_embedding)

    scores, indices = bot['index'].search(query_embedding, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < len(bot['texts']):
            results.append({
                'content': bot['texts'][idx],
                'score': float(score),
            })

    return results

def build_rag_prompt(query: str, context_chunks: List[Dict], history: List[ChatMessage], system_prompt: str = "") -> str:
    """Build the RAG prompt for Gemini."""
    if not system_prompt:
        system_prompt = (
            "You are a helpful AI assistant. Answer questions based on the provided context. "
            "If the context doesn't contain relevant information, say so honestly. "
            "Be concise, accurate, and helpful. Use markdown formatting when appropriate."
        )

    context_text = "\n\n---\n\n".join([c['content'] for c in context_chunks])

    prompt = f"""{system_prompt}

## Context from Knowledge Base:
{context_text}

## Conversation History:
"""
    for msg in history[-6:]:  # Last 6 messages for context
        role = "User" if msg.role == "user" else "Assistant"
        prompt += f"{role}: {msg.content}\n"

    prompt += f"\nUser: {query}\n\nAssistant:"

    return prompt

# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/")
async def root():
    return {"status": "ok", "service": "FMU AI Assistant API", "version": "1.0.0"}

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "gemini_models": [m['name'] for m in gemini_models],
        "openrouter_models": [m['name'] for m in openrouter_models],
        "total_fallback_models": len(all_models),
        "chatbots_loaded": len(chatbots),
        "embed_model": EMBED_MODEL_NAME,
    }

# --- Chatbot CRUD ---

@app.post("/api/chatbot")
async def create_chatbot(request: CreateChatbotRequest):
    """Create a new chatbot from chunked data."""
    chatbot_id = request.chatbot_id

    if not request.chunks:
        raise HTTPException(status_code=400, detail="No chunks provided")

    print(f"📦 Creating chatbot: {chatbot_id} with {len(request.chunks)} chunks")

    # Build FAISS index
    index, texts = build_faiss_index(request.chunks)

    # Store in memory
    chatbots[chatbot_id] = {
        'id': chatbot_id,
        'source_url': request.source_url,
        'total_chunks': len(request.chunks),
        'index': index,
        'texts': texts,
        'created_at': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        'settings': {
            'name': chatbot_id,
            'system_prompt': '',
            'temperature': 0.7,
            'initial_message': f"Hi! I'm an AI assistant trained on {request.source_url}. How can I help you?",
            'theme_color': '#6C63FF',
        },
        'chat_count': 0,
        'message_count': 0,
    }

    # Save to disk for persistence
    bot_dir = get_chatbot_dir(chatbot_id)
    bot_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(bot_dir / "index.faiss"))

    # Save metadata
    meta = {k: v for k, v in chatbots[chatbot_id].items() if k not in ('index', 'texts')}
    meta['texts'] = texts
    with open(bot_dir / "meta.json", 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"✅ Chatbot '{chatbot_id}' created successfully!")

    return {
        "status": "success",
        "chatbot_id": chatbot_id,
        "total_chunks": len(request.chunks),
        "message": f"Chatbot '{chatbot_id}' created with {len(request.chunks)} chunks",
    }


@app.get("/api/chatbots")
async def list_chatbots():
    """List all chatbots."""
    bots = []
    for bot_id, bot in chatbots.items():
        bots.append({
            'id': bot['id'],
            'name': bot['settings']['name'],
            'source_url': bot['source_url'],
            'total_chunks': bot['total_chunks'],
            'created_at': bot['created_at'],
            'chat_count': bot.get('chat_count', 0),
            'message_count': bot.get('message_count', 0),
            'settings': bot['settings'],
        })
    return {"chatbots": bots}


@app.get("/api/chatbot/{chatbot_id}")
async def get_chatbot(chatbot_id: str):
    """Get chatbot details."""
    if chatbot_id not in chatbots:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    bot = chatbots[chatbot_id]
    return {
        'id': bot['id'],
        'name': bot['settings']['name'],
        'source_url': bot['source_url'],
        'total_chunks': bot['total_chunks'],
        'created_at': bot['created_at'],
        'chat_count': bot.get('chat_count', 0),
        'message_count': bot.get('message_count', 0),
        'settings': bot['settings'],
    }


@app.put("/api/chatbot/{chatbot_id}/settings")
async def update_settings(chatbot_id: str, settings: ChatbotSettings):
    """Update chatbot settings."""
    if chatbot_id not in chatbots:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    bot = chatbots[chatbot_id]
    update_data = settings.dict(exclude_none=True)
    bot['settings'].update(update_data)

    return {"status": "success", "settings": bot['settings']}


@app.delete("/api/chatbot/{chatbot_id}")
async def delete_chatbot(chatbot_id: str):
    """Delete a chatbot."""
    if chatbot_id not in chatbots:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    del chatbots[chatbot_id]

    # Remove from disk
    bot_dir = get_chatbot_dir(chatbot_id)
    if bot_dir.exists():
        shutil.rmtree(bot_dir)

    return {"status": "success", "message": f"Chatbot '{chatbot_id}' deleted"}


# --- Chat ---

def _call_gemini(model_entry, prompt, temperature):
    """Call a Gemini model and return response text."""
    response = model_entry['model'].generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=2048,
        ),
    )
    return response.text


def _call_openrouter(model_name, prompt, temperature, history=None):
    """Call an OpenRouter model (OpenAI-compatible API) and return response text."""
    messages = [{"role": "user", "content": prompt}]

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://fmu-ai-assistant.app",
        "X-Title": "FMU AI Assistant",
    }

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 2048,
    }

    resp = httpx.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)

    if resp.status_code == 429:
        raise Exception(f"429 Rate limit exceeded for {model_name}")
    if resp.status_code != 200:
        raise Exception(f"{resp.status_code} {resp.text[:200]}")

    data = resp.json()
    return data['choices'][0]['message']['content']


@app.post("/api/chat/{chatbot_id}")
async def chat(chatbot_id: str, request: ChatRequest):
    """Send a message with automatic Gemini → OpenRouter fallback."""
    if chatbot_id not in chatbots:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    if not all_models:
        raise HTTPException(status_code=500, detail="No LLM models configured. Set GEMINI_API_KEY and/or OPENROUTER_API_KEY.")

    bot = chatbots[chatbot_id]
    bot['chat_count'] = bot.get('chat_count', 0) + 1
    bot['message_count'] = bot.get('message_count', 0) + 1

    # Retrieve relevant chunks
    context_chunks = search_chunks(chatbot_id, request.message, TOP_K)

    # Build prompt
    prompt = build_rag_prompt(
        query=request.message,
        context_chunks=context_chunks,
        history=request.history,
        system_prompt=bot['settings'].get('system_prompt', ''),
    )

    temperature = bot['settings'].get('temperature', 0.7)

    # Try each model in unified fallback chain (Gemini → OpenRouter)
    last_error = None
    for model_entry in all_models:
        model_name = model_entry['name']
        provider = model_entry['provider']

        try:
            if provider == 'gemini':
                response_text = _call_gemini(model_entry, prompt, temperature)
            elif provider == 'openrouter':
                response_text = _call_openrouter(model_name, prompt, temperature)
            else:
                continue

            print(f"  ✅ Response from [{provider}] {model_name}")
            return {
                "response": response_text,
                "model_used": f"{provider}/{model_name}",
                "sources": [{"content": c['content'][:200], "score": c['score']} for c in context_chunks[:3]],
            }

        except Exception as e:
            error_str = str(e)
            last_error = error_str
            is_quota = any(kw in error_str.lower() for kw in ['429', 'quota', 'rate limit', 'exceeded'])
            if is_quota:
                print(f"  ⚠️ [{provider}] {model_name} — quota/rate limit, trying next...")
                continue
            else:
                raise HTTPException(status_code=500, detail=f"LLM error ({provider}/{model_name}): {error_str}")

    # All models exhausted
    raise HTTPException(status_code=429, detail=f"All models exhausted (tried {len(all_models)}). Try again later. Last error: {last_error}")


# --- Startup: Load existing chatbots ---

@app.on_event("startup")
async def startup_load():
    """Load previously saved chatbots from disk."""
    data_path = Path(DATA_DIR)
    if not data_path.exists():
        data_path.mkdir(parents=True, exist_ok=True)
        return

    for bot_dir in data_path.iterdir():
        if bot_dir.is_dir() and bot_dir.name.startswith("chatbot_"):
            meta_path = bot_dir / "meta.json"
            index_path = bot_dir / "index.faiss"

            if meta_path.exists() and index_path.exists():
                try:
                    with open(meta_path) as f:
                        meta = json.load(f)

                    index = faiss.read_index(str(index_path))
                    texts = meta.pop('texts', [])

                    chatbots[meta['id']] = {
                        **meta,
                        'index': index,
                        'texts': texts,
                    }
                    print(f"  ✅ Loaded chatbot: {meta['id']}")
                except Exception as e:
                    print(f"  ⚠️ Failed to load {bot_dir.name}: {e}")

    print(f"📦 Loaded {len(chatbots)} chatbots from disk")


# =============================================================================
# Run with: uvicorn app:app --host 0.0.0.0 --port 7860
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
