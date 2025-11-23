"""
Direct API key test - bypasses all our code.
"""

import os
from pathlib import Path

# Load .env from project root (one level up if we're in tests/)
script_dir = Path(__file__).parent
if script_dir.name == 'tests':
    env_file = script_dir.parent / ".env"
else:
    env_file = script_dir / ".env"

print(f"Looking for .env at: {env_file}")
print(f".env exists: {env_file.exists()}")

if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Strip quotes if present
                value = value.strip().strip('"').strip("'")
                os.environ[key.strip()] = value
    print("✓ Loaded .env file\n")
else:
    print("✗ .env file not found!\n")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("✗ GEMINI_API_KEY not found in .env")
    print("\nMake sure your .env has:")
    print("GEMINI_API_KEY=your_key_here")
    exit(1)

print(f"API key length: {len(api_key)}")
print(f"API key starts with: {api_key[:10]}...")
print(f"API key ends with: ...{api_key[-10:]}")

# Check for quotes and whitespace
has_quotes = api_key[0] in ['"', "'"] or api_key[-1] in ['"', "'"]
has_whitespace = api_key != api_key.strip()

print(f"Has quotes: {has_quotes}")
print(f"Has whitespace: {has_whitespace}")

# Now test directly with Google's library
print("\n" + "="*60)
print("Testing with Google Generative AI library directly")
print("="*60)

try:
    import google.generativeai as genai
    
    print("\n1. Configuring with API key...")
    genai.configure(api_key=api_key)
    print("✓ Configuration accepted")
    
    print("\n2. Creating model...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✓ Model created")
    
    print("\n3. Testing simple generation...")
    response = model.generate_content("Say 'Hello World' and nothing else.")
    print(f"✓ Response received: {response.text}")
    
    print("\n" + "="*60)
    print("✓ API KEY IS VALID!")
    print("="*60)
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    print("\nPossible issues:")
    print("1. API key is incorrect")
    print("2. API key doesn't have Gemini API enabled")
    print("3. Billing not set up (Gemini requires billing)")
    print("\nGo to: https://aistudio.google.com/app/apikey")
    print("And verify your API key is active")