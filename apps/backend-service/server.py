"""
FastAPI Server - Route definitions and API endpoints
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
# from fastapi.middleware.cors import CORSMiddleware

from src.db.mongo_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    await init_db()
    print("✓ Application started successfully")

    yield

    # Shutdown
    print("✓ Application shutdown complete")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Social Commerce Platform API",
    description="API for social commerce with communities, posts, promotions, and products",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware (uncomment when needed)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Configure as needed for production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# Health check endpoint
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Social Commerce Platform API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected"
    }


# Register route modules
from src.routes import auth, supplier_auth, product, promotion, admin, order, post, community

# Authentication routes (no prefix)
app.include_router(auth.router)

# Supplier authentication routes (/supplier prefix)
app.include_router(supplier_auth.router)

# Product routes (/products prefix)
app.include_router(product.router)

# Promotion routes (/promotions prefix)
app.include_router(promotion.router)

# Admin routes (/admin prefix)
app.include_router(admin.router)

# Order routes (/orders prefix)
app.include_router(order.router)

# Post routes (/posts prefix)
app.include_router(post.router)

# Community routes (/communities prefix)
app.include_router(community.router)
