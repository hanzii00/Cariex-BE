"""
Groq API integration for detecting teeth position (upper/lower)
"""
from groq import Groq
import base64
from pathlib import Path
import os
from django.conf import settings

# Initialize Groq client with API key from settings
GROQ_API_KEY = settings.GROQ_API_KEY
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not configured in environment variables")

client = Groq(api_key=GROQ_API_KEY)


def encode_image_to_base64(image_path):
    """
    Encode an image file to base64 string.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        str: Base64 encoded image string
    """
    with open(image_path, "rb") as image_file:
        return base64.standard_b64encode(image_file.read()).decode("utf-8")


def detect_teeth_position(image_path):
    """
    Detect if teeth in the image are upper or lower using Groq API with vision.
    
    Args:
        image_path (str): Path to the dental X-ray image
        
    Returns:
        dict: Dictionary containing:
            - teeth_position: 'upper', 'lower', or 'mixed'
            - confidence: confidence score (0-1)
            - reasoning: explanation from the model
            - success: boolean indicating if detection was successful
            - error: error message if unsuccessful
    """
    try:
        # Get the file extension to determine media type
        file_ext = Path(image_path).suffix.lower()
        media_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        media_type = media_type_map.get(file_ext, 'image/jpeg')
        
        # Encode image to base64
        image_data = encode_image_to_base64(image_path)
        
        # Create message with vision capabilities
        message = client.messages.create(
            model="mixtral-8x7b-32768",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": """Analyze this dental X-ray image and determine if the teeth shown are:
1. UPPER teeth (maxilla)
2. LOWER teeth (mandible)
3. MIXED (both upper and lower visible)

Please respond in this exact JSON format:
{
    "teeth_position": "upper|lower|mixed",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation of how you determined this"
}

Only respond with the JSON, no additional text."""
                        }
                    ],
                }
            ],
        )
        
        # Parse the response
        response_text = message.content[0].text.strip()
        
        # Try to parse as JSON
        import json
        try:
            result = json.loads(response_text)
            result['success'] = True
            result['error'] = None
            return result
        except json.JSONDecodeError:
            # If response isn't valid JSON, try to extract information
            response_lower = response_text.lower()
            if 'upper' in response_lower and 'lower' not in response_lower:
                position = 'upper'
            elif 'lower' in response_lower and 'upper' not in response_lower:
                position = 'lower'
            elif 'mixed' in response_lower or ('upper' in response_lower and 'lower' in response_lower):
                position = 'mixed'
            else:
                position = 'unknown'
            
            return {
                'success': True,
                'teeth_position': position,
                'confidence': 0.7,
                'reasoning': response_text,
                'error': None
            }
            
    except FileNotFoundError:
        return {
            'success': False,
            'teeth_position': None,
            'confidence': 0,
            'reasoning': '',
            'error': f'Image file not found: {image_path}'
        }
    except Exception as e:
        return {
            'success': False,
            'teeth_position': None,
            'confidence': 0,
            'reasoning': '',
            'error': f'Error in teeth position detection: {str(e)}'
        }


def detect_teeth_position_text(description):
    """
    Detect teeth position based on a text description without image.
    Useful as a fallback or for testing.
    
    Args:
        description (str): Description of the dental image
        
    Returns:
        dict: Dictionary containing teeth position info
    """
    try:
        message = client.messages.create(
            model="mixtral-8x7b-32768",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"""Based on this description of a dental X-ray, determine if the teeth are upper or lower:

Description: {description}

Please respond in this exact JSON format:
{{
    "teeth_position": "upper|lower|mixed",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Only respond with the JSON, no additional text."""
                }
            ],
        )
        
        response_text = message.content[0].text.strip()
        
        import json
        try:
            result = json.loads(response_text)
            result['success'] = True
            result['error'] = None
            return result
        except json.JSONDecodeError:
            return {
                'success': True,
                'teeth_position': 'unknown',
                'confidence': 0.5,
                'reasoning': response_text,
                'error': None
            }
            
    except Exception as e:
        return {
            'success': False,
            'teeth_position': None,
            'confidence': 0,
            'reasoning': '',
            'error': f'Error in text-based detection: {str(e)}'
        }
