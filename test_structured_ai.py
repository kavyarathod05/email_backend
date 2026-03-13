import sys
import os
import json
import requests
from unittest.mock import MagicMock, patch

# Ensure we can import from the root directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.ai_service import generate_personalized_content

def test_ai_service_robustness():
    """Verify that generate_personalized_content correctly handles retries, multi-part responses, and schema."""
    
    # 1. Multi-part JSON fragment mock
    # This simulates the AI returning the JSON in separate parts
    mock_resp_parts = MagicMock()
    mock_resp_parts.status_code = 200
    mock_resp_parts.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [
                    {"text": '{"opening_line": "High-scale backend logic", '},
                    {"text": '"proof_line": "Built Go/Redis systems", '},
                    {"text": '"subject_lines": ["Kavya | SDE Intern"]}'}
                ]
            }
        }]
    }

    # 2. 429 Error mock
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = '{"error": {"message": "Quota exceeded"}}'

    print("--- Running Robustness Verification (429 Retry & Multi-part Joining) ---")
    
    # side_effect will return 429 first, then the multi-part success
    with patch('requests.post', side_effect=[mock_resp_429, mock_resp_parts]) as mock_post:
        # Inject dummy API key and reset cache
        import services.ai_service
        services.ai_service.GEMINI_API_KEY = "dummy_key"
        services.ai_service._company_sentence_cache = {}
        
        result = generate_personalized_content("TestCompanyRobust")
        
        print(f"Result for TestCompanyRobust: {json.dumps(result, indent=2)}")
        
        # Verify result was correctly assembled from parts
        assert result["opening_line"] == "High-scale backend logic"
        assert result["proof_line"] == "Built Go/Redis systems"
        assert "Kavya | SDE Intern" in result["subject_lines"]
        
        # Verify retry count (1 failure + 1 success)
        assert mock_post.call_count == 2 
        
        # Verify payload structure of the successful call
        _, latest_kwargs = mock_post.call_args
        payload = latest_kwargs.get('json', {})
        
        gen_config = payload.get("generationConfig", {})
        assert gen_config.get("response_mime_type") == "application/json"
        assert "response_schema" in gen_config
        assert "safetySettings" in payload
        assert payload["safetySettings"][0]["threshold"] == "BLOCK_NONE"
        
        print("✅ SUCCESS: Retry logic, multi-part joining, and payload schema verified.")

def test_json_parse_error_retry():
    """Verify that a JSON parse error triggers a retry."""
    
    # 1. Broken JSON mock
    mock_resp_broken = MagicMock()
    mock_resp_broken.status_code = 200
    mock_resp_broken.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": '{"opening_line": "Truncated...'}]
            }
        }]
    }

    # 2. Fixed JSON mock
    mock_resp_fixed = MagicMock()
    mock_resp_fixed.status_code = 200
    mock_resp_fixed.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": '{"opening_line": "Fixed", "proof_line": "Fixed", "subject_lines": []}'}]
            }
        }]
    }

    print("\n--- Running JSON Parse Error Retry Verification ---")
    
    with patch('requests.post', side_effect=[mock_resp_broken, mock_resp_fixed]) as mock_post:
        import services.ai_service
        services.ai_service._company_sentence_cache = {}
        
        result = generate_personalized_content("TestCompanyParseError")
        
        assert result["opening_line"] == "Fixed"
        assert mock_post.call_count == 2
        print("✅ SUCCESS: JSON parse error triggered retry as expected.")

if __name__ == "__main__":
    try:
        test_ai_service_robustness()
        test_json_parse_error_retry()
        print("\nALL TESTS PASSED SUCCESSFULLY.")
    except Exception as e:
        print(f"\n❌ TEST FAILURE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
