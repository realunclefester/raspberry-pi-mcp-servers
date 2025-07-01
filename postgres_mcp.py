#!/usr/bin/env python3
"""PostgreSQL MCP Server

Provides PostgreSQL database operations via MCP protocol.
"""

import asyncio
import json
import os
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
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


# Create server instance
server = Server("postgres")

# Database connection parameters
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'database': os.getenv('POSTGRES_DB', 'claude_ai_db'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD')
}

if not DB_CONFIG['password']:
    raise ValueError("POSTGRES_PASSWORD environment variable is required")


def get_connection():
    """Create database connection"""
    return psycopg2.connect(**DB_CONFIG)


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available PostgreSQL tools"""
    return [
        Tool(
            name="postgres_query",
            description="Execute a PostgreSQL query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute"
                    },
                    "params": {
                        "type": "array",
                        "description": "Query parameters (optional)",
                        "items": {
                            "type": ["string", "number", "boolean", "null"]
                        }
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="postgres_list_tables",
            description="List all tables in the database",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="postgres_describe_table",
            description="Get table schema information",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to describe"
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="postgres_insert",
            description="Insert data into a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "data": {
                        "type": "object",
                        "description": "Data to insert as key-value pairs"
                    }
                },
                "required": ["table", "data"]
            }
        ),
        Tool(
            name="postgres_update",
            description="Update data in a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "data": {
                        "type": "object",
                        "description": "Data to update as key-value pairs"
                    },
                    "where": {
                        "type": "object",
                        "description": "WHERE conditions as key-value pairs"
                    }
                },
                "required": ["table", "data", "where"]
            }
        ),
        Tool(
            name="postgres_delete",
            description="Delete data from a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "where": {
                        "type": "object",
                        "description": "WHERE conditions as key-value pairs"
                    }
                },
                "required": ["table", "where"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute PostgreSQL tools"""
    try:
        if name == "postgres_query":
            return await execute_query(arguments.get("query"), arguments.get("params"))
        
        elif name == "postgres_list_tables":
            query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """
            return await execute_query(query)
        
        elif name == "postgres_describe_table":
            table_name = arguments.get("table_name")
            query = """
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
            """
            return await execute_query(query, [table_name])
        
        elif name == "postgres_insert":
            table = arguments.get("table")
            data = arguments.get("data")
            
            columns = list(data.keys())
            values = list(data.values())
            placeholders = ["%s"] * len(values)
            
            query = f"""
                INSERT INTO {table} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING *
            """
            return await execute_query(query, values)
        
        elif name == "postgres_update":
            table = arguments.get("table")
            data = arguments.get("data")
            where = arguments.get("where")
            
            set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
            where_clause = ' AND '.join([f"{k} = %s" for k in where.keys()])
            values = list(data.values()) + list(where.values())
            
            query = f"""
                UPDATE {table}
                SET {set_clause}
                WHERE {where_clause}
                RETURNING *
            """
            return await execute_query(query, values)
        
        elif name == "postgres_delete":
            table = arguments.get("table")
            where = arguments.get("where")
            
            where_clause = ' AND '.join([f"{k} = %s" for k in where.keys()])
            values = list(where.values())
            
            query = f"""
                DELETE FROM {table}
                WHERE {where_clause}
                RETURNING *
            """
            return await execute_query(query, values)
        
        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
            
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def execute_query(query: str, params: Optional[List] = None) -> List[TextContent]:
    """Execute a PostgreSQL query"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            
            # Check if query returns data
            if cursor.description:
                results = cursor.fetchall()
                result_text = json.dumps(results, indent=2, default=str)
            else:
                # For INSERT/UPDATE/DELETE
                conn.commit()
                result_text = f"Query executed successfully. Rows affected: {cursor.rowcount}"
                
        return [TextContent(
            type="text",
            text=result_text
        )]
        
    except Exception as e:
        if conn:
            conn.rollback()
        return [TextContent(
            type="text",
            text=f"Query error: {str(e)}"
        )]
    finally:
        if conn:
            conn.close()


async def main():
    """Run the PostgreSQL MCP server"""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())