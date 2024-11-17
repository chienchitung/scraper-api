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
import urllib.parse

# 定義 User-Agents
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
]

def detect_language(text):
    if not text or not isinstance(text, str):
        return 'unknown'
    
    text = emoji.replace_emoji(text, replace='')
    
    # 檢查中文字符
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    
    # 新增：檢查文本是否只包含英文字母、數字和常見標點
    if re.match(r'^[a-zA-Z0-9\s\.,!?\'"-]+$', text):
        return 'en'
    
    # 如果上述條件都不符合，才使用 langdetect
    try:
        lang = detect(text)
        return 'en' if lang == 'en' else 'unknown'
    except LangDetectException:
        return 'unknown'

def parse_apple_url(url: str) -> tuple[str, str, str]:
    """解析 Apple Store URL"""
    try:
        # 解碼 URL
        decoded_url = urllib.parse.unquote(url)
        
        # 使用更精確的正則表達式
        pattern = r'apps\.apple\.com/(\w+)/app/[^/]+/id(\d+)'
        match = re.search(pattern, decoded_url)
        
        if not match:
            raise ValueError(f"Invalid Apple Store URL format: {url}")
            
        country_code = match.group(1)
        app_id = match.group(2)
        
        # 從 URL 提取 app_name 或使用默認值
        app_name = 'testritegroup'
        
        return country_code, app_name, app_id
    except Exception as e:
        print(f"Error parsing Apple Store URL: {str(e)}")
        raise

def get_token(country: str, app_name: str, app_id: str) -> Optional[str]:
    """獲取 Apple Store API 的 token"""
    try:
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
                token_match = re.search(r"token%22%3A%22(.+?)%22", tag)
                if token_match:
                    token = token_match.group(1)
                    break

        if not token:
            print("無法找到 token")
            return None

        return token
    except Exception as e:
        print(f"Error getting token: {str(e)}")
        return None

def fetch_apple_reviews(country: str, app_name: str, app_id: str, token: str, offset: str = '1') -> tuple[list, Optional[str], int]:
    """獲取 App Store 評論"""
    try:
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

        while retry_count < MAX_RETRIES:
            response = requests.get(request_url, headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                reviews = result.get('data', [])
                
                next_offset = None
                if 'next' in result and result['next']:
                    next_match = re.search(r"^.+offset=([0-9]+).*$", result['next'])
                    if next_match:
                        next_offset = next_match.group(1)
                
                return reviews, next_offset, response.status_code
                
            elif response.status_code == 429:
                retry_count += 1
                backoff_time = BASE_DELAY_SECS * retry_count
                print(f"達到請求限制! 重試 ({retry_count}/{MAX_RETRIES}) 等待 {backoff_time} 秒...")
                time.sleep(backoff_time)
                continue
                
            else:
                print(f"請求失敗. 回應: {response.status_code} {response.reason}")
                return [], None, response.status_code

        return [], None, 429
    except Exception as e:
        print(f"Error fetching Apple reviews: {str(e)}")
        return [], None, 500

def fetch_ios_reviews(url: str) -> List[dict]:
    try:
        print(f"Starting iOS review fetch for URL: {url}")
        country_code, app_name, app_id = parse_apple_url(url)
        
        print(f"Getting token for {country_code}/{app_name}/{app_id}")
        token = get_token(country_code, app_name, app_id)
        if not token:
            print("Failed to get token")
            return []
        
        print("Successfully got token")
        all_reviews = []
        offset = '1'
        MAX_REVIEWS = 250
        
        while offset and len(all_reviews) < MAX_REVIEWS:
            print(f"Fetching reviews with offset: {offset}")
            reviews, next_offset, status_code = fetch_apple_reviews(
                country_code, app_name, app_id, token, offset
            )
            
            if status_code != 200:
                print(f"Received non-200 status code: {status_code}")
                break
                
            processed_reviews = [{
                'date': datetime.strptime(review.get('attributes', {}).get('date', ''), '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d'),
                'username': review.get('attributes', {}).get('userName', ''),
                'review': review.get('attributes', {}).get('review', ''),
                'rating': review.get('attributes', {}).get('rating', 0),
                'platform': 'iOS',
                'developerResponse': review.get('attributes', {}).get('developerResponse', {}).get('body', ''),
                'language': detect_language(review.get('attributes', {}).get('review', ''))
            } for review in reviews]
            
            remaining_slots = MAX_REVIEWS - len(all_reviews)
            processed_reviews = processed_reviews[:remaining_slots]
            
            print(f"Processed {len(processed_reviews)} reviews")
            all_reviews.extend(processed_reviews)
            
            if len(all_reviews) >= MAX_REVIEWS:
                break
                
            offset = next_offset
            time.sleep(0.5)
            
        print(f"Total reviews collected: {len(all_reviews)}")
        
        # 按日期排序（從新到舊）
        all_reviews.sort(key=lambda x: x['date'], reverse=True)
        
        return all_reviews[:MAX_REVIEWS]
            
    except Exception as e:
        print(f"Error fetching iOS reviews: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return []

def parse_android_url(url: str) -> str:
    """解析 Google Play URL"""
    try:
        pattern = r'id=([^&]+)'
        match = re.search(pattern, url)
        if not match:
            raise ValueError(f"Invalid Google Play URL format: {url}")
        return match.group(1)
    except Exception as e:
        print(f"Error parsing Google Play URL: {str(e)}")
        raise

def fetch_android_reviews(url: str) -> List[dict]:
    try:
        MAX_REVIEWS = 250
        android_id = parse_android_url(url)
        print(f"Fetching Android reviews for app ID: {android_id}")
        
        # 取得評論
        reviews_zh = reviews_all(android_id, lang='zh_TW', country='tw')
        reviews_en = reviews_all(android_id, lang='en', country='tw')
        
        # 合併並處理評論
        all_reviews = []
        combined_reviews = (reviews_zh + reviews_en)[:MAX_REVIEWS]
        
        for review in combined_reviews:
            all_reviews.append({
                'date': review['at'].strftime('%Y-%m-%d'),
                'username': review['userName'],
                'review': review['content'],
                'rating': review['score'],
                'platform': 'Android',
                'developerResponse': review.get('replyContent', ''),
                'language': detect_language(review['content'])
            })
        
        # 按日期排序（從新到舊）
        all_reviews.sort(key=lambda x: x['date'], reverse=True)
        
        print(f"Total Android reviews collected: {len(all_reviews)}")
        return all_reviews[:MAX_REVIEWS]
        
    except Exception as e:
        print(f"Error fetching Android reviews: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return []