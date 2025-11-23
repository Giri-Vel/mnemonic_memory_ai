"""
Minimal Gemini test - loads .env explicitly from project root.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent if Path(__file__).parent.name == 'tests' else Path(__file__).parent
sys.path.insert(0, str(project_root))

print(f"Project root: {project_root}")

# Load .env explicitly
env_file = project_root / ".env"
print(f"Looking for .env at: {env_file}")
print(f".env exists: {env_file.exists()}")

if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    print("✓ Loaded .env file")
else:
    print("✗ .env file not found!")

# Now check for API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("\n✗ GEMINI_API_KEY not found in .env")
    print("Make sure your .env has a line like:")
    print("GEMINI_API_KEY=your_key_here")
    sys.exit(1)

print(f"\n✓ API key found (length: {len(api_key)})")

# Now test Gemini
print("\n" + "="*60)
print("Testing Gemini Provider")
print("="*60)

try:
    from mnemonic.llm_providers import get_provider
    import time
    
    print("\nInitializing Gemini...")
    provider = get_provider("gemini", api_key=api_key)
    print("✓ Provider initialized")
    
    # Quick continuity test
    print("\nTesting continuity check...")
    start = time.time()
    result = provider.check_continuity(
        previous_context="Debugging ChromaDB timeout issues",
        new_memory="Fixed it by increasing the timeout"
    )
    elapsed = time.time() - start
    
    print(f"Result: {'YES' if result else 'NO'} (expected YES)")
    print(f"Time: {elapsed:.2f}s")
    
    if elapsed > 3:
        print("⚠️  WARNING: Response time > 3s, might be slow in practice")
    
    print("\n" + "="*60)
    print("✓ GEMINI WORKS!")
    print("="*60)
    print("\nNext: Ready to integrate into MemorySystem")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()