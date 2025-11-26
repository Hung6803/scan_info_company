"""
Service to handle interactions with Google's Gemini API
"""
import os
import logging
import json
import google.generativeai as genai
from typing import Dict, Optional, List
from django.conf import settings

logger = logging.getLogger(__name__)

class GeminiService:
    """Service for interacting with Gemini API"""

    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            self.model = None
            return

        genai.configure(api_key=api_key)
        # Get model name from env, default to gemini-1.5-flash
        model_name = os.getenv('GEMINI_MODEL_NAME', 'gemini-2.5-flash')
        self.model = genai.GenerativeModel(model_name)

    def extract_business_info(self, text_content: str, url: str) -> Optional[Dict]:
        """
        Extract business information from text content using Gemini

        Args:
            text_content: The text content of the website
            url: The URL of the website (for context)

        Returns:
            Dict containing business info or None if failed
        """
        if not self.model:
            logger.error("Gemini model not initialized (missing API key)")
            return None

        try:
            prompt = f"""
            You are an expert data extraction AI. Your task is to extract business information from the following website text content.
            The website URL is: {url}

            Please extract the following fields:
            - name: The official name of the business.
            - phone: The phone number (format as standard Vietnamese phone number if possible).
            - email: The contact email address.
            - address: The full physical address.
            - description: A brief description of what the business does (max 200 chars).

            Rules:
            1. If a field is not found, return null.
            2. For 'name', prioritize the business name over generic titles.
            3. For 'phone', look for Vietnamese formats (09x, 02x, +84, 03x, 05x, 07x, 08x).
            4. IGNORE and DO NOT return the result if it does not have either a 'phone' or 'email'.
            5. Return ONLY a valid JSON object. Do not include markdown formatting (```json ... ```).

            Text Content:
            {text_content[:10000]}  # Limit content length to avoid token limits
            """

            response = self.model.generate_content(prompt)
            
            # Clean up response text to ensure it's valid JSON
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            data = json.loads(response_text.strip())
            
            # Strict validation: Must have phone OR email
            if not (data.get('phone') or data.get('email')):
                return None
                
            # Add source and website
            data['website'] = url
            data['source'] = 'duckduckgo_ai'
            
            return data

        except Exception as e:
            logger.error(f"Gemini extraction error for {url}: {str(e)}")
            return None

    def extract_multiple_businesses(self, text_content: str, url: str) -> List[Dict]:
        """
        Extract MULTIPLE businesses from a listing page (e.g. Top 10 list)
        """
        if not self.model:
            return []

        try:
            prompt = f"""
            You are an expert data extraction AI. The following text is from a "listing" or "directory" page that lists multiple businesses.
            The website URL is: {url}

            Your task is to extract a LIST of businesses found in the text.

            For EACH business, extract:
            - name: Business name
            - phone: Phone number
            - email: Email
            - address: Address
            - description: Brief description

            Rules:
            1. Return a JSON object with a key "businesses" containing a list of objects.
            2. Ignore businesses that don't have at least a phone number OR an email address.
            3. Return ONLY valid JSON.

            Text Content:
            {text_content[:15000]}
            """

            response = self.model.generate_content(prompt)
            
            # Clean up response
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]

            result = json.loads(response_text.strip())
            businesses = result.get('businesses', [])
            
            # Filter and add metadata
            valid_businesses = []
            for b in businesses:
                # Strict validation: Must have phone OR email
                if b.get('phone') or b.get('email'):
                    b['website'] = url
                    b['source'] = 'duckduckgo_ai'
                    valid_businesses.append(b)
            
            return valid_businesses

        except Exception as e:
            logger.error(f"Gemini multiple extraction error: {str(e)}")
            return []
