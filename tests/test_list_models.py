"""
List available Gemini models for your API key.
"""

import os
from pathlib import Path

# Load .env
script_dir = Path(__file__).parent
if script_dir.name == 'tests':
    env_file = script_dir.parent / ".env"
else:
    env_file = script_dir / ".env"

if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                os.environ[key.strip()] = value

api_key = os.getenv("GEMINI_API_KEY")

print("="*60)
print("Checking available Gemini models")
print("="*60)

try:
    import google.generativeai as genai
    
    genai.configure(api_key=api_key)
    
    print("\nAvailable models:\n")
    
    models_found = []
    for model in genai.list_models():
        # Only show models that support generateContent
        if 'generateContent' in model.supported_generation_methods:
            models_found.append(model.name)
            print(f"✓ {model.name}")
            print(f"  Description: {model.description}")
            print(f"  Methods: {', '.join(model.supported_generation_methods)}")
            print()
    
    if not models_found:
        print("✗ No models found that support generateContent")
        print("\nThis usually means:")
        print("1. API key is from an old project")
        print("2. Need to enable Gemini API in Google AI Studio")
        print("\nTry creating a NEW API key at:")
        print("https://aistudio.google.com/app/apikey")
    else:
        print("="*60)
        print(f"Found {len(models_found)} available models")
        print("="*60)
        
        # Test with the first available model
        print(f"\nTesting with: {models_found[0]}")
        model = genai.GenerativeModel(models_found[0])
        response = model.generate_content("Say hello")
        print(f"✓ Response: {response.text}")
        print("\n✓ API KEY WORKS!")
        
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()