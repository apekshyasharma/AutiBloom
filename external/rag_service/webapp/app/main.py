from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from webapp.app.routes.pages import router as pages_router
from webapp.app.routes.api_chat import router as api_router
from webapp.app.routes.admin import router as admin_router
from webapp.app.settings import WebSettings
from webapp.app.db import SQLiteConfig, init_db
from webapp.app.services.log_service import LogService
from webapp.app.services.rate_limiter import RateLimiter, RateLimitRule

# Import RAG objects 
from rag_system.config import load_settings
from rag_system.embeddings.dense import DenseEmbedder
from rag_system.retrieval.router import RetrievalRouter
from rag_system.prompting.prompt_builder import PromptBuilder
from rag_system.llm.gemini_gemma import GemmaClient
from rag_system.app.pipeline import RAGPipeline


def create_app() -> FastAPI:
    app = FastAPI(title="RAG Chatbot", version="0.1.0")

    # Configure allowed origins with CORS Middleware for deployment
    # For development: allow localhost variants
    # For production: replace with actual domain
    origins = [
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
        # Add your production domain here:
        # "https://productiondomain.com",
        # "https://www.productiondomain.com",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=600, 
    )

    app.mount("/static", StaticFiles(directory="webapp/app/static"), name="static")
    app.include_router(pages_router)
    app.include_router(api_router)
    app.include_router(admin_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.on_event("startup")
    async def startup():
        load_dotenv()

        # Load web settings (project paths)
        web_settings = WebSettings.load()
        app.state.web_settings = web_settings

        # SQLite logging DB path: artifacts/chatlogs.sqlite3
        db_path = Path(web_settings.artifacts_dir) / "chatlogs.sqlite3"
        cfg = SQLiteConfig(db_path=db_path)
        await init_db(cfg)

        # Start log service (background queue writer)
        app.state.log_service = LogService(cfg)
        await app.state.log_service.start()

        # Rate limiter 
        app.state.rate_limiter = RateLimiter(
            per_session=RateLimitRule(max_requests=12, window_seconds=60),  # 12/min per session
            per_ip=RateLimitRule(max_requests=60, window_seconds=3600),     # 60/hour per IP
        )
        
        # Load settings via existing config system
        settings = load_settings()

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY in .env")

        # Initialize components with correct signatures
        embedder = DenseEmbedder(settings.embed_model, normalize=settings.normalize_embeddings)
        router = RetrievalRouter(
            artifacts_root=settings.artifacts_dir,
            embedder=embedder,
            ef_search=settings.ef_search
        )
        pb = PromptBuilder(prompts_dir=settings.prompts_dir)
        llm = GemmaClient(api_key=api_key, model=settings.llm_model)

        app.state.settings = settings
        app.state.rag_pipeline = RAGPipeline(router=router, prompt_builder=pb, llm=llm, settings=settings)

    @app.on_event("shutdown")
    async def shutdown():
        log = getattr(app.state, "log_service", None)
        if log:
            await log.stop()

    return app


app = create_app()
