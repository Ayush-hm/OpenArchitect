# OpenArchitect

OpenArchitect turns architecture documents into reviewed architecture decisions, ADRs, and updated diagrams.

Hackathon defaults:

- Runtime: LangGraph
- Model provider: Google Gemini via AI Studio
- Architecture: modular monolith

Current pipeline:

```text
SAD / Architecture Text
  -> Architecture Extraction
  -> Graph Critic Validation
  -> Multi-Agent Review
  -> Finding Coverage Critic
  -> Architecture v2 Planning
  -> Decision-Bound ADRs
  -> Updated Mermaid Diagram
```

Run locally:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m uvicorn openarchitect.api.main:app --reload --host 127.0.0.1 --port 8000
```

Or with `uv`:

```powershell
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install --link-mode=copy -e .[dev]
uv run uvicorn openarchitect.api.main:app --reload --host 127.0.0.1 --port 8000
```

Configure `.env`:

```text
OPENARCHITECT_MODEL_PROVIDER=gemini

GEMINI_API_KEY=your-google-ai-studio-api-key
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODEL=
GEMINI_PRIMARY_TIMEOUT_SECONDS=60
GEMINI_TIMEOUT_SECONDS=180
GEMINI_MAX_TOKENS=4096
GEMINI_FORCE_JSON_RESPONSE=false
GEMINI_REASONING_EFFORT=
```

NVIDIA NIM remains available as an optional provider:

```text
OPENARCHITECT_MODEL_PROVIDER=nvidia_nim

NVIDIA_NIM_API_KEY=your-nvidia-api-key
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_NIM_MODEL=nvidia/llama-3.1-nemotron-nano-8b-v1
NVIDIA_NIM_FALLBACK_MODEL=nvidia/llama-3.3-nemotron-super-49b-v1.5
NVIDIA_NIM_PRIMARY_TIMEOUT_SECONDS=45
NVIDIA_NIM_TIMEOUT_SECONDS=180
NVIDIA_NIM_MAX_TOKENS=2048
NVIDIA_NIM_FORCE_JSON_RESPONSE=false
```

Local rule fallback is available only for development:

```powershell
$env:OPENARCHITECT_ALLOW_RULE_FALLBACK="1"
```

Example request:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/workflows/architecture-review `
  -ContentType "application/json" `
  -Body '{"document_text":"Frontend calls Backend API. Backend API reads and writes Aurora. Backend API calls Email Service synchronously."}'
```

Run the UI:

```powershell
cd frontend
npm install
npm run dev
```

The UI expects the API at `http://127.0.0.1:8000` by default. Override it with:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```
