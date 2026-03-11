---
name: Full System Architecture Map
overview: Generate a comprehensive visual architecture and flow map of the Local AI Project -- a self-hosted, ChatGPT-style chat application with private LLM inference, covering all services, data flows, authentication, database schema, and physical deployment.
todos: []
isProject: false
---

# Full System Architecture Map

Below is the complete infrastructure and architecture of your Local AI Project, broken down into multiple diagrams covering every layer.

---

## 1. High-Level Architecture (All Services)

This is the bird's-eye view of how every component connects:

```mermaid
graph TB
    subgraph browser [Browser]
        User["User (Browser)"]
    end

    subgraph machine1 ["Machine 1 — MacBook Pro 2019 (100.99.189.104)"]
        WebApp["Next.js 16 Web App\n:3000"]
        Gateway["FastAPI Gateway\n:8000"]
        subgraph supabaseSvc [Supabase Docker Stack]
            SupaAuth["Supabase Auth"]
            SupaREST["PostgREST API\n:54321"]
            Postgres["PostgreSQL\n:54322"]
            Studio["Supabase Studio\n:54323"]
            Storage["Supabase Storage"]
        end
    end

    subgraph machine2 ["Machine 2 — MacBook Pro M2 Pro (100.104.193.59)"]
        ThinkingLLM["mlx_vlm.server\nQwen 3.5 9B\n:8080"]
        InstantLLM["mlx_vlm.server\nQwen 3.5 4B\n:8081"]
    end

    User -->|"HTTPS :3000"| WebApp
    WebApp -->|"Supabase Auth SDK"| SupaAuth
    WebApp -->|"REST + JWT\n:8000"| Gateway
    Gateway -->|"REST + JWT (RLS)\n:54321"| SupaREST
    SupaREST --> Postgres
    SupaAuth --> Postgres
    Storage --> Postgres
    Gateway -->|"HTTP /chat/completions\nvia Tailscale :8080"| ThinkingLLM
    Gateway -->|"HTTP /chat/completions\nvia Tailscale :8081"| InstantLLM
```



**Key points:**

- Two physical machines connected via **Tailscale VPN**
- Machine 1 runs the web app, gateway, and entire Supabase stack (via Docker)
- Machine 2 runs the GPU inference servers (Apple Silicon MLX)
- All inter-service communication is HTTP; no message queues or gRPC

---

## 2. Request Flow — Chat Completion (Streaming)

The main user-facing flow when sending a chat message:

```mermaid
sequenceDiagram
    participant U as Browser
    participant W as Next.js :3000
    participant G as Gateway :8000
    participant DB as Supabase/Postgres
    participant LLM as mlx_vlm :8080

    U->>W: Type message, click Send
    W->>W: Get JWT from Supabase Auth session
    W->>G: POST /chat/stream {message, mode, session_id}<br/>Authorization: Bearer JWT

    G->>G: Decode JWT, extract user_id
    G->>DB: GET or CREATE chat_session (via REST + RLS)
    DB-->>G: session_id

    G->>DB: INSERT chat_message (role=user)
    G->>DB: SELECT last 20 messages for context

    G->>LLM: POST /chat/completions<br/>{model, messages[], stream:true,<br/>enable_thinking, thinking_budget}

    loop SSE Streaming
        LLM-->>G: data: {delta.content, delta.reasoning_content}
        G-->>W: data: {delta.content, delta.reasoning_content}
        W-->>U: Render markdown incrementally
    end

    LLM-->>G: data: [DONE]
    G->>G: Strip think tags, extract reasoning_content
    G->>DB: INSERT chat_message (role=assistant,<br/>content, reasoning_content, mode_used)
    G-->>W: data: [DONE]
    W->>W: Parse think tags, show reasoning toggle
    W-->>U: Final rendered response
```



---

## 3. Authentication Flow

```mermaid
sequenceDiagram
    participant U as Browser
    participant W as Next.js :3000
    participant SA as Supabase Auth
    participant G as Gateway :8000

    U->>W: Navigate to /login
    U->>W: Enter email + password
    W->>SA: signInWithPassword(email, password)
    SA-->>W: JWT access_token + refresh_token
    W->>W: Store tokens in cookie (via @supabase/ssr)

    U->>W: Navigate to /chat
    W->>W: Read JWT from cookie
    W->>G: GET /chat/sessions<br/>Authorization: Bearer JWT
    G->>G: Decode JWT (HS256)<br/>Extract sub (user_id), email, role
    G->>G: Attach user_id to request context
    G-->>W: 200 OK + session list
```



**Auth details:**

- Supabase Auth issues JWTs (HS256, shared secret)
- Gateway decodes JWT locally (no round-trip to Supabase Auth for validation)
- All Supabase DB queries pass the user JWT for Row-Level Security enforcement
- In dev mode, signature verification is skipped for convenience

---

## 4. Inference Mode Routing

```mermaid
flowchart TD
    Req["Incoming Chat Request"]
    Mode{"mode parameter?"}

    Req --> Mode
    Mode -->|"instant"| Instant["Instant Tier\nQwen 3.5 4B\n:8081"]
    Mode -->|"thinking"| Thinking["Thinking Tier\nQwen 3.5 9B\n:8080\nbudget: 2048 tokens"]
    Mode -->|"thinking_harder"| Harder["Thinking Tier\nQwen 3.5 9B\n:8080\nbudget: 8192 tokens\nmax_tokens: 28672"]

    Thinking -->|"fails?"| Fallback{"Fallback enabled?"}
    Harder -->|"fails?"| Fallback
    Fallback -->|"yes"| Instant
    Fallback -->|"no"| Error["Return Error"]

    Instant --> Resp["Return Response"]
    Thinking --> Resp
    Harder --> Resp
```



**Cost controls:**

- `THINKING_DAILY_REQUEST_LIMIT` caps heavy inference per day
- `THINKING_MAX_CONCURRENT` limits parallel thinking requests
- Fallback to instant tier is configurable via `ROUTING_THINKING_FALLBACK_TO_INSTANT`

---

## 5. Database Schema (ER Diagram)

```mermaid
erDiagram
    auth_users {
        uuid id PK
        text email
        jsonb raw_user_meta_data
    }

    profiles {
        uuid id PK,FK
        text email
        text name
        text avatar_url
        timestamptz created_at
        timestamptz updated_at
    }

    chat_sessions {
        uuid id PK
        uuid user_id FK
        text title
        boolean is_archived
        timestamptz created_at
        timestamptz updated_at
    }

    chat_messages {
        uuid id PK
        uuid session_id FK
        uuid user_id FK
        text role
        text content
        text reasoning_content
        text mode_used
        integer tokens_used
        timestamptz created_at
    }

    documents {
        uuid id PK
        uuid user_id FK
        text filename
        text storage_path
        text file_type
        integer file_size
        text status
        timestamptz created_at
        timestamptz processed_at
    }

    document_chunks {
        uuid id PK
        uuid document_id FK
        uuid user_id FK
        text content
        vector embedding
        integer chunk_index
        timestamptz created_at
    }

    auth_users ||--|| profiles : "trigger creates"
    profiles ||--o{ chat_sessions : "owns"
    chat_sessions ||--o{ chat_messages : "contains"
    profiles ||--o{ chat_messages : "authored by"
    profiles ||--o{ documents : "uploads"
    documents ||--o{ document_chunks : "split into"
    profiles ||--o{ document_chunks : "owns"
```



**Key schema features:**

- Row-Level Security on every table (users only see their own data)
- `auth.users` trigger auto-creates a `profiles` row on signup
- `chat_messages` trigger auto-updates `chat_sessions.updated_at`
- pgvector extension with IVFFlat index for RAG similarity search (future)
- `mode_used` supports: `instant`, `thinking`, `thinking_harder`

---

## 6. Physical Deployment / Network Topology

```mermaid
graph LR
    subgraph tailnet [Tailscale VPN Mesh]
        subgraph mbp2019 ["MacBook Pro 2019\n100.99.189.104"]
            next["Next.js :3000"]
            fastapi["FastAPI :8000"]
            supa["Supabase Docker\n:54321 / :54322 / :54323"]
        end
        subgraph mbpM2 ["MacBook Pro M2 Pro\n100.104.193.59"]
            thinking["mlx_vlm Thinking :8080"]
            instant["mlx_vlm Instant :8081"]
        end
    end

    next --- fastapi
    fastapi --- supa
    fastapi ---|"Tailscale"| thinking
    fastapi ---|"Tailscale"| instant
```



---

## 7. Frontend Page Structure

```mermaid
flowchart TD
    Root["/ (root page.tsx)"]
    Root -->|"authenticated?"| Chat["/chat\nMain Chat UI"]
    Root -->|"not authenticated"| Login["/login\nSign In / Sign Up"]

    Chat --> Sidebar["Session Sidebar\n(list, rename, delete)"]
    Chat --> ChatArea["Chat Area\n(messages, streaming)"]
    Chat --> ModeSelect["Mode Selector\n(instant / thinking / thinking_harder)"]

    ChatArea --> Markdown["react-markdown\n+ syntax highlighting"]
    ChatArea --> ThinkBlock["Collapsible Reasoning\n(think tag parser)"]
```



**Frontend stack:** Next.js 16 (App Router), React 19, Tailwind CSS v4, Geist Mono font, dark glass UI theme with green accents. State is managed purely with React hooks (no external state library).

---

## Summary Table

- **Web App** -- Next.js 16, port 3000 -- Chat UI, auth, session management
- **Gateway** -- FastAPI, port 8000 -- Auth middleware, routing, DB proxy, inference proxy, SSE streaming
- **Supabase** -- Docker stack, ports 54321-54323 -- Auth (JWT), PostgreSQL (RLS), Storage (documents bucket)
- **Thinking LLM** -- mlx_vlm.server, port 8080 -- Qwen 3.5 9B with chain-of-thought reasoning
- **Instant LLM** -- mlx_vlm.server, port 8081 -- Qwen 3.5 4B for fast responses
- **Tailscale** -- VPN mesh connecting both machines
- **RAG (future)** -- pgvector + document_chunks table with embedding similarity search

The gateway is the central orchestrator: it authenticates every request, manages sessions/messages in Supabase, routes to the appropriate inference tier, handles streaming, extracts reasoning content, and applies cost controls.