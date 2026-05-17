import sys
import os
import json
import requests
from unittest.mock import MagicMock, patch

# Ensure we can import from the root directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.ai_service import generate_personalized_content

def test_ai_service_robustness():
    """Verify that generate_personalized_content correctly handles multi-part responses, and schema."""
    
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

    print("--- Running Robustness Verification (Multi-part Joining) ---")
    
    # side_effect will return the multi-part success
    with patch('requests.post', side_effect=[mock_resp_parts]) as mock_post:
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
        
        # Verify attempt count (1 success)
        assert mock_post.call_count == 1 
        
        # Verify payload structure of the successful call
        _, latest_kwargs = mock_post.call_args
        payload = latest_kwargs.get('json', {})
        
        gen_config = payload.get("generationConfig", {})
        assert gen_config.get("response_mime_type") == "application/json"
        assert "response_schema" in gen_config
        assert "safetySettings" in payload
        assert payload["safetySettings"][0]["threshold"] == "BLOCK_NONE"
        
        print("✅ SUCCESS: Multi-part joining and payload schema verified.")

def test_json_parse_error_no_retry():
    """Verify that a JSON parse error returns empty {} without retrying."""
    
    # 1. Broken JSON mock
    mock_resp_broken = MagicMock()
    mock_resp_broken.status_code = 200
    mock_resp_broken.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": '{"opening_line": "Irreparable" [ { ## BAD JSON ##'}]
            }
        }]
    }

    print("\n--- Running JSON Parse Error Verification ---")
    
    with patch('requests.post', side_effect=[mock_resp_broken]) as mock_post:
        import services.ai_service
        services.ai_service._company_sentence_cache = {}
        
        result = generate_personalized_content("TestCompanyParseError")
        
        assert result == {}
        assert mock_post.call_count == 1
        print("✅ SUCCESS: JSON parse error handled gracefully.")

if __name__ == "__main__":
    try:
        test_ai_service_robustness()
        test_json_parse_error_no_retry()
        print("\nALL TESTS PASSED SUCCESSFULLY.")
    except Exception as e:
        print(f"\n❌ TEST FAILURE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
