from typing import List, Optional
from datetime import datetime
import re
from google_play_scraper import reviews_all
import emoji
from langdetect import detect, LangDetectException
import requests
import json
import random
import time
from tqdm import tqdm

# 定義 User-Agents
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
]

def detect_language(text):
    if not text or not isinstance(text, str):
        return 'unknown'
    
    text = emoji.replace_emoji(text, replace='')
    
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    
    try:
        lang = detect(text)
        return 'en' if lang == 'en' else 'unknown'
    except LangDetectException:
        return 'unknown'

def get_token(country: str, app_name: str, app_id: str) -> Optional[str]:
    """獲取 Apple Store API 的 token"""
    response = requests.get(
        f'https://apps.apple.com/{country}/app/{app_name}/id{app_id}',
        headers={'User-Agent': random.choice(user_agents)}
    )

    if response.status_code != 200:
        print(f"GET request failed. Response: {response.status_code} {response.reason}")
        return None

    tags = response.text.splitlines()
    token = None
    for tag in tags:
        if re.match(r"<meta.+web-experience-app/config/environment", tag):
            token = re.search(r"token%22%3A%22(.+?)%22", tag).group(1)
            break

    if not token:
        print("無法找到 token")
        return None

    return token

def fetch_apple_reviews(country: str, app_name: str, app_id: str, token: str, offset: str = '1') -> tuple[list, Optional[str], int]:
    """獲取 App Store 評論"""
    landing_url = f'https://apps.apple.com/{country}/app/{app_name}/id{app_id}'
    request_url = f'https://amp-api.apps.apple.com/v1/catalog/{country}/apps/{app_id}/reviews'

    headers = {
        'Accept': 'application/json',
        'Authorization': f'bearer {token}',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://apps.apple.com',
        'Referer': landing_url,
        'User-Agent': random.choice(user_agents)
    }

    params = (
        ('l', 'zh-TW'),
        ('offset', str(offset)),
        ('limit', '20'),
        ('platform', 'web'),
        ('additionalPlatforms', 'appletv,ipad,iphone,mac')
    )

    retry_count = 0
    MAX_RETRIES = 5
    BASE_DELAY_SECS = 10
    reviews = []

    while retry_count < MAX_RETRIES:
        response = requests.get(request_url, headers=headers, params=params)
        
        if response.status_code == 200:
            result = response.json()
            reviews = result.get('data', [])
            
            # 獲取下一頁的 offset
            next_offset = None
            if 'next' in result and result['next']:
                next_match = re.search(r"^.+offset=([0-9]+).*$", result['next'])
                if next_match:
                    next_offset = next_match.group(1)
            
            return reviews, next_offset, response.status_code
            
        elif response.status_code == 429:  # 達到請求限制
            retry_count += 1
            backoff_time = BASE_DELAY_SECS * retry_count
            print(f"達到請求限制! 重試 ({retry_count}/{MAX_RETRIES}) 等待 {backoff_time} 秒...")
            time.sleep(backoff_time)
            continue
            
        else:
            print(f"請求失敗. 回應: {response.status_code} {response.reason}")
            return [], None, response.status_code

    return [], None, 429

def fetch_ios_reviews(url: str) -> List[dict]:
    try:
        print(f"Starting iOS review fetch for URL: {url}")
        pattern = r'apps\.apple\.com/(\w+)/app/([^/]+)/id(\d+)'
        match = re.search(pattern, url)
        if not match:
            print("URL pattern did not match")
            return []
            
        country_code = match.group(1)
        app_name = 'ikea'
        app_id = match.group(3)
        
        print(f"Getting token for {country_code}/{app_name}/{app_id}")
        token = get_token(country_code, app_name, app_id)
        if not token:
            print("Failed to get token")
            return []
        
        print("Successfully got token")
        all_reviews = []
        offset = '1'
        MAX_REVIEWS = 100000
        
        while offset and int(offset) <= MAX_REVIEWS:
            print(f"Fetching reviews with offset: {offset}")
            reviews, next_offset, status_code = fetch_apple_reviews(
                country_code, app_name, app_id, token, offset
            )
            
            if status_code != 200:
                print(f"Received non-200 status code: {status_code}")
                break
                
            processed_reviews = [{
                'date': review.get('attributes', {}).get('date', ''),
                'username': review.get('attributes', {}).get('userName', ''),
                'review': review.get('attributes', {}).get('review', ''),
                'rating': review.get('attributes', {}).get('rating', 0),
                'platform': 'iOS',
                'developerResponse': review.get('attributes', {}).get('developerResponse', {}).get('body', ''),
                'language': detect_language(review.get('attributes', {}).get('review', ''))
            } for review in reviews]
            
            print(f"Processed {len(processed_reviews)} reviews")
            all_reviews.extend(processed_reviews)
            offset = next_offset
            
            time.sleep(0.5)
            
        print(f"Total reviews collected: {len(all_reviews)}")
        return all_reviews
            
    except Exception as e:
        print(f"Error fetching iOS reviews: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return []

def fetch_android_reviews(url: str) -> List[dict]:
    try:
        android_id = url.split('id=')[1].split('&')[0]
        reviews_zh = reviews_all(android_id, lang='zh_TW', country='tw')
        reviews_en = reviews_all(android_id, lang='en', country='tw')
        
        all_reviews = []
        for review in reviews_zh + reviews_en:
            all_reviews.append({
                'date': review['at'].strftime('%Y-%m-%d'),
                'username': review['userName'],
                'review': review['content'],
                'rating': review['score'],
                'platform': 'Android',
                'developerResponse': review.get('replyContent', ''),
                'language': detect_language(review['content'])
            })
            
        return all_reviews
        
    except Exception as e:
        print(f"Error fetching Android reviews: {str(e)}")
        return []