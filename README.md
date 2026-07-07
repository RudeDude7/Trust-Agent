# 🛡️ Trust Agent: Autonomous Vendor Due Diligence Platform

![Architecture: Multi-Agent](https://img.shields.io/badge/Architecture-LangGraph_Multi--Agent-purple?style=for-the-badge)
![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Frontend: React](https://img.shields.io/badge/Frontend-React_Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Database: Supabase](https://img.shields.io/badge/Database-Supabase_pgvector-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)

An autonomous AI platform designed to streamline and automate third-party vendor risk assessments. By orchestrating a swarm of specialized AI agents, **Trust Agent** evaluates vendors against internal corporate security policies, gathers live threat intelligence, and generates comprehensive risk scorecards in minutes instead of weeks.

## ✨ Key Features

- 🧠 **Multi-Agent Orchestration**: Built on **LangGraph**, the system coordinates specialized AI agents (OSINT Researcher, RAG Analyst, Security Judge) that autonomously handle distinct phases of the audit lifecycle.
- 🔍 **Hierarchical RAG Pipeline**: Ingests massive PDF policies into Supabase `pgvector`. It uses a custom parent-child chunking strategy with zero-cost local embeddings (`all-MiniLM-L6-v2`) for high-recall vector retrieval.
- 🌐 **Automated OSINT Gathering**: Dynamically queries the web (via the Exa API) for real-time vendor breach reports, SOC2 audit statuses, and security news.
- ⚡ **Real-Time Streaming UI**: A modern React (Vite) frontend with Tailwind CSS that streams the AI agents' internal thought processes and progress via Server-Sent Events (SSE).
- 🔒 **Live Threat Intelligence**: A proactive threat feed that continuously monitors "watched" vendors for emerging security vulnerabilities.
- 🚀 **Full-Stack CI/CD**: Automated deployment pipeline using GitHub Actions to deploy the Dockerized FastAPI backend to Hugging Face Spaces and the React frontend to Vercel.

## 🏗️ Architecture & Tech Stack

### Backend (Python / FastAPI)
- **Framework**: FastAPI (async ASGI framework)
- **AI/LLM**: LangChain, LangGraph, Google Gemini API
- **Embeddings**: Local HuggingFace embeddings (`sentence-transformers`) for cost-effective, high-privacy vectorization.
- **Search**: Exa API for neural web search.

### Database (Supabase / PostgreSQL)
- **Vector DB**: `pgvector` for approximate nearest neighbor (HNSW) search on document chunks.
- **Auth & Storage**: Supabase Auth (JWT) and PostgreSQL JSONB columns for flexible chat history and gap action storage.
- **Security**: Strict Row-Level Security (RLS) ensuring strict tenant isolation.

### Frontend (React / TypeScript)
- **Framework**: React 18, Vite, TypeScript
- **Styling**: Tailwind CSS (custom `stone-50` and `accent-600` minimalist aesthetic)
- **Icons**: Lucide React

## 📂 Repository Structure

```text
├── backend/                  # FastAPI Application & LangGraph Agents
│   ├── agent.py              # Core multi-agent state graph definition
│   ├── api.py                # FastAPI endpoints and SSE streaming
│   ├── ingest.py             # Hierarchical RAG PDF ingestion pipeline
│   ├── osint_agent.py        # Web-scraping and research agent
│   ├── rag_agent.py          # Document retrieval and analysis agent
│   └── judge_agent.py        # Final risk scoring and synthesis agent
├── frontend/                 # React UI
│   ├── src/components/       # Modular UI components (Wizard, Sidebar, LiveThreats)
│   └── src/api.ts            # Centralized API client interacting with the backend
├── db/                       # Database Schemas & Migrations
│   └── schema.sql            # Core pgvector tables and HNSW index setup
├── tests/                    # Backend automated test suite
└── .github/workflows/        # CI/CD Pipeline (deploy-backend.yml)
```

## 🚀 Deployment

The platform is designed for scalable cloud deployment:
1. **Backend**: Containerized via Docker and automatically deployed to Hugging Face Spaces via GitHub Actions (`git subtree split`).
2. **Frontend**: Deployed continuously to Vercel, securely communicating with the backend via environment-aware API abstraction.
3. **Database**: Hosted on Supabase Serverless PostgreSQL.

## 🔒 Security & Privacy

Trust Agent is built with zero-trust principles. All internal policy documents are embedded locally using CPU-bound models, ensuring that proprietary company security standards never leak to third-party cloud embedding providers. 