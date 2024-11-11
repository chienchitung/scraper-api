from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scraper import fetch_ios_reviews, fetch_android_reviews
import os
from typing import Optional

app = FastAPI()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生產環境中應該限制為你的 Vercel 域名
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

@app.post("/scrape")
async def scrape_reviews(
    request: ScrapeRequest,
    api_key: str = Depends(verify_api_key)
):
    try:
        ios_reviews = []
        android_reviews = []

        if request.appleStore:
            ios_reviews = fetch_ios_reviews(request.appleStore)
        
        if request.googlePlay:
            android_reviews = fetch_android_reviews(request.googlePlay)

        return {
            "success": True,
            "data": ios_reviews + android_reviews
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000"))) 