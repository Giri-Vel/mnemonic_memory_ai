"""
Basic CLI for Mnemonic
"""

import argparse
from mnemonic.core.memory import SimpleMemory

def main():
    parser = argparse.ArgumentParser(description="Mnemonic - Your AI Memory")
    parser.add_argument('command', choices=['store', 'search', 'list'])
    parser.add_argument('content', nargs='*', help='Content to store or search')
    
    args = parser.parse_args()
    mem = SimpleMemory()
    
    if args.command == 'store':
        content = ' '.join(args.content)
        mem_id = mem.store(content)
        print(f"✓ Stored memory #{mem_id}")
    
    elif args.command == 'search':
        query = ' '.join(args.content)
        results = mem.search(query)
        print(f"Found {len(results)} memories:")
        for r in results:
            print(f"  [{r['id']}] {r['content'][:60]}...")
    
    elif args.command == 'list':
        memories = mem.retrieve_all()
        print(f"Total memories: {len(memories)}")
        for m in memories[-10:]:  # Last 10
            print(f"  [{m['id']}] {m['content'][:60]}...")

if __name__ == "__main__":
    main()