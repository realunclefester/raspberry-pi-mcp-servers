#!/usr/bin/env python3
"""
Simplified Node-RED MCP Server - Read-only operations and flow triggering
Provides search, inspection and execution capabilities without modification rights
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional
import httpx
from mcp.server import Server
from mcp.types import Tool, TextContent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Node-RED configuration
NODE_RED_URL = os.getenv('NODE_RED_URL', 'http://localhost:1880')
NODE_RED_FLOWS_API = f"{NODE_RED_URL}/flows"

# Create server instance
server = Server("node-red-mcp-simple")

async def get_flows(flow_id: Optional[str] = None) -> Dict[str, Any]:
    """Get flows from Node-RED"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{NODE_RED_FLOWS_API}/{flow_id}" if flow_id else NODE_RED_FLOWS_API
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Failed to get flows: {e}")
        return {"error": str(e)}

async def search_nodes(search_term: str) -> Dict[str, Any]:
    """Search for nodes by name, type, or content"""
    try:
        flows = await get_flows()
        if isinstance(flows, dict) and "error" in flows:
            return flows
        
        results = []
        search_lower = search_term.lower()
        
        for node in flows:
            # Skip flow tabs
            if node.get("type") == "tab":
                continue
                
            # Search in various fields
            if (search_lower in node.get("name", "").lower() or
                search_lower in node.get("type", "").lower() or
                search_lower in node.get("info", "").lower() or
                search_lower in str(node.get("func", "")).lower() or
                search_lower in str(node.get("url", "")).lower() or
                search_lower in str(node.get("query", "")).lower()):
                
                # Get flow name
                flow_name = "Unknown"
                for flow in flows:
                    if flow.get("type") == "tab" and flow.get("id") == node.get("z"):
                        flow_name = flow.get("label", "Unnamed Flow")
                        break
                
                results.append({
                    "id": node.get("id"),
                    "type": node.get("type"),
                    "name": node.get("name", ""),
                    "flow": flow_name,
                    "flow_id": node.get("z"),
                    "x": node.get("x"),
                    "y": node.get("y")
                })
        
        return {
            "search_term": search_term,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        return {"error": f"Search failed: {e}"}

async def get_node_details(node_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific node"""
    try:
        flows = await get_flows()
        if isinstance(flows, dict) and "error" in flows:
            return flows
        
        for node in flows:
            if node.get("id") == node_id:
                # Add flow information
                if node.get("z"):
                    for flow in flows:
                        if flow.get("type") == "tab" and flow.get("id") == node.get("z"):
                            node["flow_name"] = flow.get("label", "Unnamed Flow")
                            break
                return node
        
        return {"error": f"Node {node_id} not found"}
    except Exception as e:
        return {"error": f"Failed to get node details: {e}"}

async def inject_trigger(node_id: str) -> Dict[str, Any]:
    """Trigger an inject node"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{NODE_RED_URL}/inject/{node_id}")
            return {"triggered": node_id, "status": response.status_code}
    except Exception as e:
        return {"error": str(e)}

async def get_context(scope: str, key: Optional[str] = None) -> Dict[str, Any]:
    """Get context variables"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{NODE_RED_URL}/context/{scope}"
            if key:
                url += f"/{key}"
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}

async def analyze_flows() -> Dict[str, Any]:
    """Analyze flows and provide statistics"""
    try:
        flows = await get_flows()
        if isinstance(flows, dict) and "error" in flows:
            return flows
        
        # Statistics
        flow_count = 0
        node_count = 0
        node_types = {}
        flows_info = []
        
        for item in flows:
            if item.get("type") == "tab":
                flow_count += 1
                # Count nodes in this flow
                flow_nodes = [n for n in flows if n.get("z") == item.get("id")]
                flows_info.append({
                    "id": item.get("id"),
                    "name": item.get("label", "Unnamed"),
                    "disabled": item.get("disabled", False),
                    "node_count": len(flow_nodes)
                })
            else:
                node_count += 1
                node_type = item.get("type", "unknown")
                node_types[node_type] = node_types.get(node_type, 0) + 1
        
        return {
            "flow_count": flow_count,
            "node_count": node_count,
            "node_types": node_types,
            "flows": flows_info
        }
    except Exception as e:
        return {"error": f"Analysis failed: {e}"}

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available Node-RED tools"""
    return [
        Tool(
            name="node_red_get_flows",
            description="Get all flows or a specific flow by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "flow_id": {
                        "type": "string",
                        "description": "Optional flow ID to get specific flow"
                    }
                }
            }
        ),
        Tool(
            name="node_red_search_nodes",
            description="Search for nodes by name, type, or content",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Term to search for in node properties"
                    }
                },
                "required": ["search_term"]
            }
        ),
        Tool(
            name="node_red_get_node_details",
            description="Get detailed information about a specific node",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "ID of the node to inspect"
                    }
                },
                "required": ["node_id"]
            }
        ),
        Tool(
            name="node_red_inject_trigger",
            description="Trigger an inject node to execute a flow",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "ID of the inject node to trigger"
                    }
                },
                "required": ["node_id"]
            }
        ),
        Tool(
            name="node_red_get_context",
            description="Get flow/global context variables",
            inputSchema={
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["global", "flow"],
                        "description": "Context scope"
                    },
                    "key": {
                        "type": "string",
                        "description": "Optional key to get specific value"
                    }
                },
                "required": ["scope"]
            }
        ),
        Tool(
            name="node_red_analyze_flows",
            description="Analyze all flows and provide statistics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    try:
        if name == "node_red_get_flows":
            result = await get_flows(arguments.get("flow_id"))
        elif name == "node_red_search_nodes":
            result = await search_nodes(arguments["search_term"])
        elif name == "node_red_get_node_details":
            result = await get_node_details(arguments["node_id"])
        elif name == "node_red_inject_trigger":
            result = await inject_trigger(arguments["node_id"])
        elif name == "node_red_get_context":
            result = await get_context(arguments["scope"], arguments.get("key"))
        elif name == "node_red_analyze_flows":
            result = await analyze_flows()
        else:
            result = {"error": f"Unknown tool: {name}"}
            
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
    except Exception as e:
        logger.error(f"Error in {name}: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

async def main():
    """Main entry point"""
    # Test Node-RED connection at startup
    try:
        logger.info("Testing Node-RED connection...")
        test_result = await get_flows()
        if "error" not in test_result:
            logger.info(f"Node-RED connection successful")
            # Analyze flows at startup
            stats = await analyze_flows()
            if "error" not in stats:
                logger.info(f"Node-RED: {stats.get('flow_count', 0)} flows, {stats.get('node_count', 0)} nodes")
        else:
            logger.warning(f"Node-RED connection issue: {test_result}")
    except Exception as e:
        logger.error(f"Node-RED connection failed: {e}")
    
    # Run the MCP server
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())