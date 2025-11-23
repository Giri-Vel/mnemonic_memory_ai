#!/usr/bin/env python3
"""
gap_analyzer.py

Detect bridge opportunities (entities that can connect different communities) in the mnemonic knowledge
graph stored in a sqlite DB (mnemonic.db). Outputs text or JSON. Supports a focus mode that concentrates
analysis around a single entity name.

Usage:
  python gap_analyzer.py <mnemonic.db> [--format text|json] [--focus "entity name"] [--min-degree N]

Heuristics used:
 - Build adjacency list from relationships table.
 - For each entity, gather neighbor community_ids (if available). Bridge score = number of distinct neighbor
   community_ids (excluding the entity's own community if set) weighted by degree and centrality.
 - Candidates are ranked by a simple score: (distinct_neighbor_communities) * log(1 + degree) * (1 + centrality).

Outputs:
 - Top bridge candidates with details
 - Focus mode suggests specific entities to connect to

"""

import sqlite3
import argparse
import json
import math
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


def load_entities(conn) -> Dict[int, Dict]:
    cur = conn.cursor()
    cur.execute("SELECT id, name, type, frequency, community_id, centrality FROM entities")
    entities = {}
    for row in cur.fetchall():
        ent_id, name, ent_type, freq, community_id, centrality = row
        entities[ent_id] = {
            "id": ent_id,
            "name": name,
            "type": ent_type,
            "frequency": freq or 0,
            "community_id": community_id,
            "centrality": centrality or 0.0,
        }
    return entities


def load_relationships(conn) -> List[Tuple[int, int]]:
    cur = conn.cursor()
    cur.execute("SELECT entity1_id, entity2_id FROM relationships")
    rels = []
    for a, b in cur.fetchall():
        try:
            rels.append((int(a), int(b)))
        except Exception:
            continue
    return rels


def build_adjacency(rels: List[Tuple[int, int]]) -> Dict[int, set]:
    adj = defaultdict(set)
    for a, b in rels:
        adj[a].add(b)
        adj[b].add(a)
    return adj


def compute_bridge_scores(entities: Dict[int, Dict], adj: Dict[int, set], min_degree: int = 1) -> List[Dict]:
    results = []
    for ent_id, meta in entities.items():
        neighbors = adj.get(ent_id, set())
        degree = len(neighbors)
        if degree < min_degree:
            continue

        neighbor_communities = set()
        example_neighbors = []

        for n in list(neighbors)[:20]:
            n_comm = entities.get(n, {}).get("community_id")
            if n_comm is not None:
                neighbor_communities.add(n_comm)
            example_neighbors.append({
                "id": n,
                "name": entities.get(n, {}).get("name"),
                "community_id": entities.get(n, {}).get("community_id")
            })

        own_comm = meta.get("community_id")
        if own_comm in neighbor_communities:
            neighbor_communities.discard(own_comm)

        distinct = len(neighbor_communities)
        centrality = meta.get("centrality") or 0.0
        score = distinct * math.log(1 + degree) * (1 + float(centrality))

        results.append({
            "id": ent_id,
            "name": meta.get("name"),
            "type": meta.get("type"),
            "community_id": own_comm,
            "degree": degree,
            "distinct_neighbor_communities": distinct,
            "centrality": centrality,
            "bridge_score": score,
            "example_neighbors": example_neighbors,
        })

    results.sort(key=lambda x: x["bridge_score"], reverse=True)
    return results


def recommend_for_focus(focus_name: str, entities: Dict[int, Dict], adj: Dict[int, set],
                        bridge_candidates: List[Dict], top_k: int = 5) -> Dict:

    found = [e for e in entities.values() if (e.get("name") or "").lower() == focus_name.lower()]
    if not found:
        found = [e for e in entities.values() if focus_name.lower() in (e.get("name") or "").lower()]

    if not found:
        return {"focus": focus_name, "found": False, "message": "No matching entity found."}

    focus = found[0]
    fid = focus["id"]
    f_comm = focus.get("community_id")
    f_neighbors = adj.get(fid, set())

    suggestions = []
    for cand in bridge_candidates:
        cid = cand["id"]
        if cid == fid:
            continue
        if cid in f_neighbors:
            continue

        c_comm = cand.get("community_id")
        if c_comm is None or f_comm is None or c_comm != f_comm:
            suggestions.append(cand)

    suggestions = suggestions[:top_k]
    detailed = []

    for s in suggestions:
        s_id = s["id"]
        sn = adj.get(s_id, set())
        neighbor_samples = []

        for n in sorted(list(sn), key=lambda x: len(adj.get(x, [])), reverse=True)[:5]:
            neighbor_samples.append({
                "id": n,
                "name": entities.get(n, {}).get("name"),
                "community_id": entities.get(n, {}).get("community_id")
            })

        detailed.append({
            "candidate": s,
            "suggest_link_to": neighbor_samples,
            "reason": f"Connects to {s['distinct_neighbor_communities']} communities; degree {s['degree']}"
        })

    return {
        "focus": focus_name,
        "found": True,
        "focus_entity": focus,
        "suggestions": detailed,
    }


def pretty_text_output(bridge_candidates: List[Dict], focus_result: Optional[Dict], top_n: int = 10):
    lines = []
    lines.append("=" * 60)
    lines.append("BRIDGE OPPORTUNITIES — Top candidates")
    lines.append("=" * 60)

    if not bridge_candidates:
        return "No candidates found."

    for i, c in enumerate(bridge_candidates[:top_n], 1):
        lines.append(f"{i}. {c['name']} (id:{c['id']})")
        lines.append(f"   type: {c['type']} | comm: {c['community_id']} | degree: {c['degree']} | centrality: {c['centrality']:.3f}")
        lines.append(f"   distinct neighbor communities: {c['distinct_neighbor_communities']} | bridge score: {c['bridge_score']:.3f}")
        ex = c.get("example_neighbors", [])[:6]
        if ex:
            lines.append("   neighbors: " + ", ".join(
                [f"{e['name']}[id:{e['id']}|comm:{e['community_id']}]" for e in ex]
            ))
        lines.append("")

    if focus_result:
        lines.append("=" * 60)
        lines.append(f"FOCUS: {focus_result.get('focus')}")
        if not focus_result.get("found"):
            lines.append("  No matching entity found.")
        else:
            f = focus_result.get("focus_entity")
            lines.append(f"  Found: {f.get('name')} (id:{f.get('id')}) community:{f.get('community_id')}")
            lines.append("  Suggested connections:")
            for s in focus_result.get("suggestions", []):
                cand = s["candidate"]
                lines.append(f"   - Link to {cand['name']} (id:{cand['id']}) — {s['reason']}")
                targets = s["suggest_link_to"]
                if targets:
                    lines.append("     via: " + ", ".join(
                        [f"{t['name']}[id:{t['id']}|comm:{t['community_id']}]" for t in targets]
                    ))
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--focus", type=str, default=None)
    parser.add_argument("--min-degree", type=int, default=2)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path)
    entities = load_entities(conn)
    rels = load_relationships(conn)
    adj = build_adjacency(rels)

    for eid, meta in entities.items():
        meta["degree"] = len(adj.get(eid, set()))

    bridge_candidates = compute_bridge_scores(entities, adj, min_degree=args.min_degree)
    focus_result = recommend_for_focus(args.focus, entities, adj, bridge_candidates, top_k=args.top) if args.focus else None

    if args.format == "json":
        out = {
            "meta": {
                "db": args.db_path,
                "generated_at": __import__("datetime").datetime.now().isoformat(),
                "min_degree": args.min_degree,
                "top_n": args.top,
                "focus": args.focus,
            },
            "bridge_candidates": bridge_candidates[:args.top],
            "focus": focus_result,
        }
        print(json.dumps(out, indent=2))
    else:
        print(pretty_text_output(bridge_candidates, focus_result, top_n=args.top))


if __name__ == "__main__":
    main()
