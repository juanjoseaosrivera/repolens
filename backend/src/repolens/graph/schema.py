"""Neo4j graph schema constants and setup queries.

Graph schema:
  Nodes:  :File, :Function, :Class
  Relationships:  :IMPORTS, :CALLS, :DEFINES
"""

# Constraint and index setup (idempotent)
SETUP_QUERIES: list[str] = [
    # Unique constraints
    "CREATE CONSTRAINT IF NOT EXISTS FOR (f:File) REQUIRE (f.repo_id, f.path) IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (fn:Function) "
    "REQUIRE (fn.repo_id, fn.qualified_name) IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Class) REQUIRE (c.repo_id, c.qualified_name) IS UNIQUE",
    # Indexes for lookup
    "CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.repo_id)",
    "CREATE INDEX IF NOT EXISTS FOR (fn:Function) ON (fn.repo_id)",
    "CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.repo_id)",
]

# Cleanup query for re-ingestion
CLEANUP_QUERY = """
MATCH (n {repo_id: $repo_id})
DETACH DELETE n
"""
