from typing import List, Optional
from datetime import datetime
import re
from google_play_scraper import reviews_all
import emoji
from langdetect import detect, LangDetectException
from apple_app_reviews_scraper import get_token, fetch_reviews

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

def fetch_ios_reviews(url: str) -> List[dict]:
    try:
        pattern = r'apps\.apple\.com/(\w+)/app/([^/]+)/id(\d+)'
        match = re.search(pattern, url)
        if not match:
            return []
            
        country_code = match.group(1)
        app_name = 'ikea'
        app_id = match.group(3)
        
        token = get_token(country_code, app_name, app_id)
        if not token:
            return []
            
        all_reviews = []
        offset = '1'
        
        while offset:
            reviews, offset, _ = fetch_reviews(
                country=country_code,
                app_name=app_name,
                app_id=app_id,
                token=token,
                offset=offset
            )
            all_reviews.extend(reviews)
            
        return [{
            'date': review['date'],
            'username': review['username'],
            'review': review['review'],
            'rating': review['rating'],
            'platform': 'iOS',
            'developerResponse': review.get('developerResponse', ''),
            'language': detect_language(review['review'])
        } for review in all_reviews]
            
    except Exception as e:
        print(f"Error fetching iOS reviews: {str(e)}")
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