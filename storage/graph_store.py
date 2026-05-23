"""Neo4j graph store adapter."""

from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

from config import load_settings


class Neo4jGraphStore:
    """Neo4j-backed symbol graph for code navigation."""

    def __init__(self) -> None:
        settings = load_settings()
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        """Close Neo4j driver connection."""
        self.driver.close()

    def build_graph(self, symbol_table: dict[str, dict], repo_name: str) -> None:
        """Build or update graph for a repo from AST symbol table."""
        with self.driver.session() as session:
            for file_path, entry in symbol_table.items():
                session.run(
                    """
                    MERGE (f:File {repo_name: $repo_name, path: $file_path})
                    """,
                    repo_name=repo_name,
                    file_path=file_path,
                )

                for fn_name in entry.get("functions", []):
                    session.run(
                        """
                        MERGE (f:File {repo_name: $repo_name, path: $file_path})
                        MERGE (fn:Function {repo_name: $repo_name, name: $fn_name})
                        MERGE (f)-[:DEFINES]->(fn)
                        """,
                        repo_name=repo_name,
                        file_path=file_path,
                        fn_name=fn_name,
                    )

                for cls_name in entry.get("classes", []):
                    session.run(
                        """
                        MERGE (f:File {repo_name: $repo_name, path: $file_path})
                        MERGE (c:Class {repo_name: $repo_name, name: $cls_name})
                        MERGE (f)-[:DEFINES]->(c)
                        """,
                        repo_name=repo_name,
                        file_path=file_path,
                        cls_name=cls_name,
                    )

                for import_stmt in entry.get("imports", []):
                    session.run(
                        """
                        MERGE (f:File {repo_name: $repo_name, path: $file_path})
                        MERGE (imp:File {repo_name: $repo_name, path: $import_stmt})
                        MERGE (f)-[:IMPORTS]->(imp)
                        """,
                        repo_name=repo_name,
                        file_path=file_path,
                        import_stmt=import_stmt,
                    )

                for call in entry.get("calls", []):
                    caller = call["caller"] if isinstance(call, dict) else call[0]
                    callee = call["callee"] if isinstance(call, dict) else call[1]
                    session.run(
                        """
                        MERGE (a:Function {repo_name: $repo_name, name: $caller})
                        MERGE (b:Function {repo_name: $repo_name, name: $callee})
                        MERGE (a)-[:CALLS]->(b)
                        """,
                        repo_name=repo_name,
                        caller=caller,
                        callee=callee,
                    )

                for inherit in entry.get("inherits", []):
                    child = inherit["class"] if isinstance(inherit, dict) else inherit[0]
                    base = inherit["base"] if isinstance(inherit, dict) else inherit[1]
                    session.run(
                        """
                        MERGE (c1:Class {repo_name: $repo_name, name: $child})
                        MERGE (c2:Class {repo_name: $repo_name, name: $base})
                        MERGE (c1)-[:INHERITS]->(c2)
                        """,
                        repo_name=repo_name,
                        child=child,
                        base=base,
                    )

    def get_neighbors(self, symbol_name: str, repo_name: str, depth: int = 2) -> list[dict[str, Any]]:
        """Return graph neighbors around a symbol up to depth hops."""
        with self.driver.session() as session:
            records = session.run(
                """
                MATCH (n {repo_name: $repo_name, name: $symbol_name})
                MATCH p=(n)-[*1..$depth]-(m {repo_name: $repo_name})
                RETURN DISTINCT labels(m) AS labels, coalesce(m.name, m.path) AS value
                """,
                repo_name=repo_name,
                symbol_name=symbol_name,
                depth=depth,
            )
            return [{"labels": r["labels"], "value": r["value"]} for r in records]

    def get_callers(self, function_name: str, repo_name: str) -> list[str]:
        """Return function names that call the given function."""
        with self.driver.session() as session:
            records = session.run(
                """
                MATCH (caller:Function {repo_name: $repo_name})-[:CALLS]->(callee:Function {repo_name: $repo_name, name: $function_name})
                RETURN DISTINCT caller.name AS name
                ORDER BY name
                """,
                repo_name=repo_name,
                function_name=function_name,
            )
            return [r["name"] for r in records]

    def get_callees(self, function_name: str, repo_name: str) -> list[str]:
        """Return function names called by the given function."""
        with self.driver.session() as session:
            records = session.run(
                """
                MATCH (caller:Function {repo_name: $repo_name, name: $function_name})-[:CALLS]->(callee:Function {repo_name: $repo_name})
                RETURN DISTINCT callee.name AS name
                ORDER BY name
                """,
                repo_name=repo_name,
                function_name=function_name,
            )
            return [r["name"] for r in records]

    def delete_repo_graph(self, repo_name: str) -> None:
        """Delete all graph nodes and relationships for a repo."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (n {repo_name: $repo_name})
                DETACH DELETE n
                """,
                repo_name=repo_name,
            )
