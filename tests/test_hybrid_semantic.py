#!/usr/bin/env python3
"""
Compare semantic-only vs hybrid search results.
Run this to see the difference in action!
"""
from mnemonic.memory_system import MemorySystem

def compare_search_methods(query):
    """Compare semantic vs hybrid search for a query."""
    system = MemorySystem()
    
    print("=" * 70)
    print(f"Query: '{query}'")
    print("=" * 70)
    
    # Get results from both methods
    semantic_results = system.semantic_search(query, n_results=5)
    hybrid_results = system.hybrid_search(query, n_results=5)
    
    # Display semantic results
    print("\n🔵 SEMANTIC ONLY (Current Method):")
    print("-" * 70)
    if not semantic_results:
        print("No results found.")
    else:
        for i, result in enumerate(semantic_results, 1):
            memory = result['memory']
            score = result['relevance_score']
            content = memory['content'][:60]
            print(f"{i}. [{score:.2f}] {content}...")
    
    # Display hybrid results
    print("\n🟢 HYBRID SEARCH (85% semantic + 15% keyword):")
    print("-" * 70)
    if not hybrid_results:
        print("No results found.")
    else:
        for i, result in enumerate(hybrid_results, 1):
            memory = result['memory']
            hybrid_score = result['hybrid_score']
            semantic_score = result['semantic_score']
            keyword_score = result['keyword_score']
            content = memory['content'][:60]
            
            print(f"{i}. [{hybrid_score:.2f}] {content}...")
            print(f"   📊 Semantic: {semantic_score:.2f} | Keyword: {keyword_score:.2f}")
    
    print("\n")


def main():
    """Run comparison tests."""
    print("\n" + "=" * 70)
    print("HYBRID SEARCH COMPARISON TEST")
    print("=" * 70)
    
    # Test different query types
    test_queries = [
        "machine learning",           # Conceptual (semantic should dominate)
        "Sarah Johnson",              # Proper noun (keyword should boost)
        "December 15",                # Date (keyword should boost)
        "API",                        # Acronym (hybrid catches both)
        "project deadline",           # Mixed (both methods useful)
    ]
    
    for query in test_queries:
        compare_search_methods(query)
        input("Press Enter to continue...")
    
    print("=" * 70)
    print("Comparison complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()