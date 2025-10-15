"""
Mnemonic CLI - Command line interface for memory operations
"""

import argparse
from mnemonic.core.memory import SimpleMemory

def main():
    parser = argparse.ArgumentParser(
        description="Mnemonic - Your Personal AI Memory System"
    )
    parser.add_argument(
        'command', 
        choices=['store', 'search', 'list', 'stats'],
        help='Command to execute'
    )
    parser.add_argument(
        'content', 
        nargs='*', 
        help='Content to store or search query'
    )
    
    args = parser.parse_args()
    mem = SimpleMemory()
    
    if args.command == 'store':
        if not args.content:
            print("❌ Error: No content provided to store")
            return
        content = ' '.join(args.content)
        mem_id = mem.store(content)
        print(f"✅ Stored memory #{mem_id}")
        print(f"   '{content[:60]}{'...' if len(content) > 60 else ''}'")
    
    elif args.command == 'search':
        if not args.content:
            print("❌ Error: No search query provided")
            return
        query = ' '.join(args.content)
        results = mem.search(query)
        
        if not results:
            print(f"🔍 No memories found for '{query}'")
        else:
            print(f"🔍 Found {len(results)} memories for '{query}':\n")
            for r in results:
                print(f"  [{r['id']}] {r['content']}")
                print(f"      📅 {r['timestamp']}\n")
    
    elif args.command == 'list':
        memories = mem.retrieve_all()
        if not memories:
            print("📝 No memories stored yet")
        else:
            print(f"📝 Total memories: {len(memories)}\n")
            # Show last 10
            for m in memories[-10:]:
                print(f"  [{m['id']}] {m['content'][:70]}{'...' if len(m['content']) > 70 else ''}")
                print(f"      📅 {m['timestamp']}\n")
            
            if len(memories) > 10:
                print(f"  ... and {len(memories) - 10} more")
    
    elif args.command == 'stats':
        memories = mem.retrieve_all()
        print(f"📊 Memory Statistics:\n")
        print(f"  Total memories: {len(memories)}")
        if memories:
            total_chars = sum(len(m['content']) for m in memories)
            avg_length = total_chars / len(memories)
            print(f"  Average length: {avg_length:.0f} characters")
            print(f"  First memory: {memories[0]['timestamp']}")
            print(f"  Latest memory: {memories[-1]['timestamp']}")

if __name__ == "__main__":
    main()