from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scraper import fetch_ios_reviews, fetch_android_reviews
import os
from typing import Optional

app = FastAPI(
    title="Scraper API",
    description="API for scraping app reviews",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 金鑰驗證
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="Authorization")

def verify_api_key(api_key: str = Security(api_key_header)):
    if not API_KEY:
        return
    if api_key.replace("Bearer ", "") != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Could not validate credentials"
        )
    return api_key

class ScrapeRequest(BaseModel):
    appleStore: Optional[str] = None
    googlePlay: Optional[str] = None

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/scrape")
async def scrape_reviews(
    request: ScrapeRequest,
    api_key: str = Depends(verify_api_key)
):
    try:
        print(f"Received request: {request}")
        ios_reviews = []
        android_reviews = []

        if request.appleStore:
            print(f"Fetching iOS reviews from: {request.appleStore}")
            ios_reviews = fetch_ios_reviews(request.appleStore)
            print(f"Found {len(ios_reviews)} iOS reviews")
        
        if request.googlePlay:
            print(f"Fetching Android reviews from: {request.googlePlay}")
            android_reviews = fetch_android_reviews(request.googlePlay)
            print(f"Found {len(android_reviews)} Android reviews")

        result = {
            "success": True,
            "data": ios_reviews + android_reviews
        }
        print(f"Returning {len(result['data'])} total reviews")
        return result
    except Exception as e:
        print(f"Error in scrape_reviews: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", "1"))
    timeout = int(os.getenv("TIMEOUT", "300"))
    
    print(f"Starting server on port {port} with {workers} workers")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        workers=workers,
        timeout_keep_alive=timeout,
        log_level="info"
    )