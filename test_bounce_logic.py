import os
import requests
from unittest.mock import patch
from dotenv import load_dotenv

load_dotenv()

# Mocking the GAS bridge URL if not set
os.environ.setdefault("GOOGLE_SCRIPT_URL", "https://script.google.com/macros/s/mock/exec")

def test_blacklist_check():
    """
    Test the is_blacklisted function with a mock response.
    """
    from services.email_sender import is_blacklisted
    
    with patch("requests.post") as mock_post:
        # Mocking a blacklisted response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"success": True, "blacklisted": True}
        
        result = is_blacklisted("test@example.com")
        print(f"Test 1 (Blacklisted): {'PASSED' if result is True else 'FAILED'}")
        
        # Mocking a non-blacklisted response
        mock_post.return_value.json.return_value = {"success": True, "blacklisted": False}
        result = is_blacklisted("new@example.com")
        print(f"Test 2 (Not Blacklisted): {'PASSED' if result is False else 'FAILED'}")

if __name__ == "__main__":
    test_blacklist_check()
