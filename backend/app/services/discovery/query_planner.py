"""Query Planner for generating autonomous discovery searches."""

from typing import List, Set
from app.models.search_profile import SearchProfile

class QueryPlanner:
    def __init__(self, max_queries: int = 15):
        self.max_queries = max_queries

    def plan_queries(self, profile: SearchProfile) -> List[str]:
        """Deterministically generate and deduplicate bounded search queries."""
        roles = profile.target_roles or []
        roles.extend(profile.role_aliases or [])
        roles = [r for r in roles if r]
        
        if not roles:
            # Fallback if no specific roles
            roles = ["Engineer"]
            
        locations = profile.preferred_countries or []
        locations.extend(profile.preferred_cities or [])
        locations = [l for l in locations if l]
        if not locations:
            locations = ["Remote"]
            
        keywords = profile.keywords or []
        keywords = [k for k in keywords if k]
        
        # Build base queries using deterministic cartesian product (roles x locations)
        generated: Set[str] = set()
        queries: List[str] = []
        
        def add_query(q: str):
            q_clean = " ".join(q.split()).lower()
            if q_clean not in generated and len(queries) < self.max_queries:
                generated.add(q_clean)
                queries.append(q)
                
        # Primary pass: Role + Location
        for role in roles:
            for loc in locations:
                base = f"{role} {loc}"
                add_query(base)
                
        # Secondary pass: Include top keywords to mix it up if capacity remains
        if len(queries) < self.max_queries and keywords:
            for role in roles:
                for keyword in keywords[:3]:
                    for loc in locations[:2]:
                        base = f"{role} {keyword} {loc}"
                        add_query(base)
                        
        # Tertiary pass: Just Role (global)
        if len(queries) < self.max_queries:
            for role in roles:
                add_query(role)
                
        return queries
