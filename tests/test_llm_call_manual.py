"""
Quick manual test for Gemini provider.

Run this BEFORE integrating into MemorySystem to verify:
1. Your API key works
2. Response times are acceptable
3. Continuity decisions make sense
"""

import os
import time
from mnemonic.llm_providers import get_provider


def test_gemini_setup():
    """Verify Gemini API key and connectivity."""
    print("=" * 60)
    print("GEMINI PROVIDER VALIDATION")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n✗ GEMINI_API_KEY not found in environment")
        print("Add it to your .env file:")
        print("  GEMINI_API_KEY=your_key_here")
        return False
    
    print(f"\n✓ API key found (length: {len(api_key)})")
    
    # Initialize provider
    try:
        print("\nInitializing Gemini provider...")
        provider = get_provider("gemini", api_key=api_key)
        print("✓ Provider initialized")
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        return False
    
    return provider


def test_continuity_check(provider):
    """Test continuity checking with real scenarios."""
    print("\n" + "=" * 60)
    print("TEST 1: Continuity Check")
    print("=" * 60)
    
    # Test case 1: Clear continuity (SHOULD BE YES)
    print("\n1. Testing RELATED memories (expect YES):")
    print("   Previous: 'Debugging ChromaDB connection timeout issues'")
    print("   New:      'Fixed it by increasing timeout to 30 seconds'")
    
    start = time.time()
    result = provider.check_continuity(
        previous_context="Debugging ChromaDB connection timeout issues",
        new_memory="Fixed it by increasing timeout to 30 seconds"
    )
    elapsed = time.time() - start
    
    print(f"   Result: {'YES ✓' if result else 'NO ✗'}")
    print(f"   Time: {elapsed:.2f}s")
    
    if not result:
        print("   ⚠ WARNING: Expected YES but got NO")
    
    # Test case 2: No continuity (SHOULD BE NO)
    print("\n2. Testing UNRELATED memories (expect NO):")
    print("   Previous: 'Debugging ChromaDB connection timeout issues'")
    print("   New:      'Made pasta for dinner with garlic bread'")
    
    start = time.time()
    result = provider.check_continuity(
        previous_context="Debugging ChromaDB connection timeout issues",
        new_memory="Made pasta for dinner with garlic bread"
    )
    elapsed = time.time() - start
    
    print(f"   Result: {'YES ✓' if not result else 'NO ✗'}")
    print(f"   Time: {elapsed:.2f}s")
    
    if result:
        print("   ⚠ WARNING: Expected NO but got YES")
    
    # Test case 3: Ambiguous (could go either way)
    print("\n3. Testing AMBIGUOUS memories:")
    print("   Previous: 'Working on entity extraction pipeline'")
    print("   New:      'Took a break and went for a walk'")
    
    start = time.time()
    result = provider.check_continuity(
        previous_context="Working on entity extraction pipeline",
        new_memory="Took a break and went for a walk"
    )
    elapsed = time.time() - start
    
    print(f"   Result: {'YES' if result else 'NO'}")
    print(f"   Time: {elapsed:.2f}s")
    print("   (Either answer is reasonable here)")


def test_summary_generation(provider):
    """Test summary generation."""
    print("\n" + "=" * 60)
    print("TEST 2: Summary Generation")
    print("=" * 60)
    
    memories = [
        "Started working on adding session support to Mnemonic",
        "Created database migration for sessions table",
        "Implemented LLM provider abstraction with Gemini",
        "Built SessionStore for managing session lifecycle",
        "Wrote tests and verified everything works"
    ]
    
    print("\nGenerating summary for 5 memories...")
    print("(This might take 2-3 seconds)")
    
    start = time.time()
    summary = provider.generate_summary(
        memories=memories,
        topic="Session implementation"
    )
    elapsed = time.time() - start
    
    print(f"\nTime: {elapsed:.2f}s")
    print(f"\nSummary ({len(summary)} chars):")
    print("-" * 60)
    print(summary)
    print("-" * 60)


def test_topic_suggestion(provider):
    """Test topic suggestion."""
    print("\n" + "=" * 60)
    print("TEST 3: Topic Suggestion")
    print("=" * 60)
    
    memories = [
        "Debugged why entity extraction was missing some names",
        "Found issue in GLiNER confidence threshold",
        "Adjusted threshold from 0.7 to 0.5",
        "Re-ran extraction and got better results"
    ]
    
    print("\nSuggesting topic for memories about entity extraction...")
    
    start = time.time()
    topic = provider.suggest_topic(memories)
    elapsed = time.time() - start
    
    print(f"\nTime: {elapsed:.2f}s")
    print(f"Suggested topic: \"{topic}\"")


def main():
    """Run all validation tests."""
    
    # Test setup
    provider = test_gemini_setup()
    if not provider:
        print("\n✗ Setup failed - fix API key and try again")
        return
    
    # Run tests
    try:
        test_continuity_check(provider)
        test_summary_generation(provider)
        test_topic_suggestion(provider)
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Review the results above")
        print("2. If response times are acceptable (< 3s)")
        print("3. And continuity decisions look reasonable")
        print("4. Then we're ready to integrate into MemorySystem!")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()