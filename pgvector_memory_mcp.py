#!/usr/bin/env python3
"""Memory MCP Server - PostgreSQL pgvector

Combines embeddings and PostgreSQL pgvector for high-level memory operations.
Provides simple functions for storing and searching system memory.
"""

import asyncio
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncpg
import httpx  # Still needed for embeddings API
import logging
from pathlib import Path

from mcp.server import Server
from mcp.types import Tool, TextContent

# Load .env file if it exists
env_path = Path('/home/rpi/docker/.env')
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create server instance
server = Server("memory")

# Service URLs
EMBEDDINGS_URL = os.getenv('EMBEDDINGS_URL', 'http://localhost:8001')
# QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')  # Replaced by PostgreSQL
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    # Build DATABASE_URL from individual components
    password = os.getenv('POSTGRES_PASSWORD')
    if password:
        DATABASE_URL = f"postgresql://postgres:{password}@localhost:5432/claude_ai_db"
    else:
        raise ValueError("DATABASE_URL or POSTGRES_PASSWORD environment variable is required")
TABLE_NAME = 'claude_os_system'  # pgvector table name


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available memory tools"""
    return [
        Tool(
            name="store_memory",
            description="Store text in vector memory with metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to store in memory"
                    },
                    "type": {
                        "type": "string", 
                        "description": "Type of information (hardware, workflow, project, etc.)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category (system_memory, user_preference, troubleshooting)",
                        "default": "system_memory"
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority level (high, medium, low)",
                        "default": "medium"
                    }
                },
                "required": ["text", "type"]
            }
        ),
        Tool(
            name="search_memory",
            description="Search vector memory for relevant information",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 5
                    },
                    "type_filter": {
                        "type": "string",
                        "description": "Filter by information type (optional)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="list_memory_types",
            description="List all available memory types and counts",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="memory_stats",
            description="Get memory collection statistics",
            inputSchema={
                "type": "object", 
                "properties": {},
                "required": []
            }
        )
    ]


async def get_embedding(text: str) -> List[float]:
    """Get embedding from embeddings service"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{EMBEDDINGS_URL}/embed",
                json={"texts": [text]},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data["embeddings"][0]
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return []


async def get_db_connection():
    """Get PostgreSQL connection"""
    return await asyncpg.connect(DATABASE_URL)


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    
    if name == "store_memory":
        text = arguments["text"]
        info_type = arguments["type"] 
        category = arguments.get("category", "system_memory")
        priority = arguments.get("priority", "medium")
        
        # Get embedding
        embedding = await get_embedding(text)
        if not embedding:
            return [TextContent(type="text", text="Error: Failed to generate embedding")]
        
        # Store in pgvector
        conn = await get_db_connection()
        try:
            # Generate unique ID
            memory_id = str(int(datetime.now().timestamp() * 1000000))  # microsecond timestamp as string
            
            # Convert embedding list to pgvector string format
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
            
            await conn.execute(
                f"""
                INSERT INTO {TABLE_NAME} (id, text, type, category, priority, embedding, created_at)
                VALUES ($1, $2, $3, $4, $5, $6::vector(384), $7)
                """,
                memory_id, text, info_type, category, priority, embedding_str, datetime.now()
            )
            
            return [TextContent(
                type="text", 
                text=f"Memory stored successfully with ID: {memory_id}"
            )]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error storing memory: {e}")]
        finally:
            await conn.close()
    
    elif name == "search_memory":
        query = arguments["query"]
        limit = arguments.get("limit", 5)
        type_filter = arguments.get("type_filter")
        
        # Get query embedding
        embedding = await get_embedding(query)
        if not embedding:
            return [TextContent(type="text", text="Error: Failed to generate query embedding")]
        
        # Convert embedding list to pgvector string format
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        # Search in pgvector
        conn = await get_db_connection()
        try:
            if type_filter:
                # Search with type filter
                rows = await conn.fetch(
                    f"""
                    SELECT id, text, type, category, priority, created_at,
                           embedding <=> $1::vector(384) as distance
                    FROM {TABLE_NAME} 
                    WHERE type = $2
                    ORDER BY distance
                    LIMIT $3
                    """,
                    embedding_str, type_filter, limit
                )
            else:
                # Search without filter
                rows = await conn.fetch(
                    f"""
                    SELECT id, text, type, category, priority, created_at,
                           embedding <=> $1::vector(384) as distance  
                    FROM {TABLE_NAME}
                    ORDER BY distance
                    LIMIT $2
                    """,
                    embedding_str, limit
                )
            
            if not rows:
                return [TextContent(type="text", text="No relevant memories found")]
            
            results = []
            for row in rows:
                similarity = 1 - row["distance"]  # Convert distance to similarity
                results.append({
                    "id": row["id"],
                    "text": row["text"],
                    "type": row["type"],
                    "category": row["category"],
                    "priority": row["priority"],
                    "created_at": row["created_at"].isoformat(),
                    "similarity": round(similarity, 4)
                })
            
            return [TextContent(
                type="text",
                text=f"Found {len(results)} relevant memories:\n\n" +
                     "\n".join([
                         f"• [{r['type']}] {r['text'][:100]}{'...' if len(r['text']) > 100 else ''} "
                         f"(similarity: {r['similarity']})"
                         for r in results
                     ])
            )]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching memory: {e}")]
        finally:
            await conn.close()
    
    elif name == "list_memory_types":
        conn = await get_db_connection()
        try:
            rows = await conn.fetch(
                f"""
                SELECT type, COUNT(*) as count
                FROM {TABLE_NAME} 
                GROUP BY type 
                ORDER BY type
                """
            )
            
            if not rows:
                return [TextContent(type="text", text="No memory types found")]
            
            result = "Memory types:\n\n"
            for row in rows:
                result += f"• {row['type']}: {row['count']} entries\n"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error listing memory types: {e}")]
        finally:
            await conn.close()
    
    elif name == "memory_stats":
        conn = await get_db_connection()
        try:
            # Get overall stats
            stats = await conn.fetchrow(
                f"""
                SELECT 
                    COUNT(*) as total_vectors,
                    COUNT(DISTINCT type) as unique_types,
                    COUNT(DISTINCT category) as unique_categories,
                    MIN(created_at) as oldest_entry,
                    MAX(created_at) as newest_entry
                FROM {TABLE_NAME}
                """
            )
            
            if stats["total_vectors"] == 0:
                return [TextContent(type="text", text="Memory collection is empty")]
            
            result = f"""Memory Statistics:
            
• Total vectors: {stats['total_vectors']}
• Unique types: {stats['unique_types']}
• Unique categories: {stats['unique_categories']}
• Oldest entry: {stats['oldest_entry'].strftime('%Y-%m-%d %H:%M:%S') if stats['oldest_entry'] else 'N/A'}
• Newest entry: {stats['newest_entry'].strftime('%Y-%m-%d %H:%M:%S') if stats['newest_entry'] else 'N/A'}
• Collection name: {TABLE_NAME}
• Vector dimension: 384
"""
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting memory stats: {e}")]
        finally:
            await conn.close()
    
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Main entry point"""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())