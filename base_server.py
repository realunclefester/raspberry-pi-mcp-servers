#!/usr/bin/env python3
"""Base MCP Server

Provides a base class for implementing MCP servers with common functionality.
"""

import asyncio
import json
import logging
import sys
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server


class BaseMCPServer(ABC):
    """Base class for MCP servers with common functionality"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """Initialize base MCP server
        
        Args:
            name: Server name
            version: Server version
        """
        self.name = name
        self.version = version
        self.server = Server(name)
        self.logger = self._setup_logging()
        
        # Register handlers
        self.server.list_tools()(self.handle_list_tools)
        self.server.call_tool()(self.handle_call_tool)
        
        # Initialize server
        self._initialize()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the server"""
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.INFO)
        
        # Console handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            f'[{self.name}] %(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
        
    def _initialize(self):
        """Initialize server - can be overridden by subclasses"""
        self.logger.info(f"Initializing {self.name} MCP server v{self.version}")
        
    @abstractmethod
    def get_tools(self) -> List[Tool]:
        """Get list of tools provided by this server
        
        Must be implemented by subclasses.
        
        Returns:
            List of Tool objects
        """
        pass
        
    @abstractmethod
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a specific tool
        
        Must be implemented by subclasses.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool execution result (any JSON-serializable data)
        """
        pass
        
    async def handle_list_tools(self) -> List[Tool]:
        """Handle list_tools request"""
        try:
            tools = self.get_tools()
            self.logger.debug(f"Listing {len(tools)} tools")
            return tools
        except Exception as e:
            self.logger.error(f"Error listing tools: {e}")
            raise
            
    async def handle_call_tool(self, name: str, arguments: Dict[str, Any]) -> List[Union[TextContent, ImageContent]]:
        """Handle call_tool request"""
        try:
            self.logger.info(f"Executing tool: {name}")
            self.logger.debug(f"Arguments: {json.dumps(arguments, indent=2)}")
            
            # Execute tool
            result = await self.execute_tool(name, arguments)
            
            # Convert result to appropriate content type
            content = self._format_result(result)
            
            self.logger.debug(f"Tool {name} executed successfully")
            return content
            
        except Exception as e:
            self.logger.error(f"Error executing tool {name}: {e}")
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": str(e),
                    "tool": name,
                    "timestamp": datetime.utcnow().isoformat()
                }, indent=2)
            )]
            
    def _format_result(self, result: Any) -> List[Union[TextContent, ImageContent]]:
        """Format tool result as MCP content
        
        Args:
            result: Tool execution result
            
        Returns:
            List of content objects
        """
        # Handle different result types
        if isinstance(result, str):
            return [TextContent(type="text", text=result)]
        elif isinstance(result, bytes):
            # Assume image data
            return [ImageContent(type="image", data=result)]
        elif isinstance(result, list) and all(isinstance(item, (TextContent, ImageContent)) for item in result):
            # Already formatted as content list
            return result
        else:
            # Convert to JSON
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )]
            
    async def run(self):
        """Run the MCP server"""
        self.logger.info(f"Starting {self.name} MCP server v{self.version}")
        
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options()
                )
        except KeyboardInterrupt:
            self.logger.info("Server stopped by user")
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            raise
            
    def create_tool(self, 
                   name: str,
                   description: str,
                   parameters: Optional[Dict[str, Any]] = None,
                   required: Optional[List[str]] = None) -> Tool:
        """Helper to create a tool definition
        
        Args:
            name: Tool name
            description: Tool description
            parameters: Parameter definitions
            required: Required parameter names
            
        Returns:
            Tool object
        """
        input_schema = {
            "type": "object",
            "properties": parameters or {},
            "required": required or []
        }
        
        return Tool(
            name=name,
            description=description,
            inputSchema=input_schema
        )


# Example implementation
class ExampleMCPServer(BaseMCPServer):
    """Example MCP server implementation"""
    
    def __init__(self):
        super().__init__("example", "1.0.0")
        
    def get_tools(self) -> List[Tool]:
        """Get available tools"""
        return [
            self.create_tool(
                name="echo",
                description="Echo back the input message",
                parameters={
                    "message": {
                        "type": "string",
                        "description": "Message to echo"
                    }
                },
                required=["message"]
            ),
            self.create_tool(
                name="get_time",
                description="Get current time",
                parameters={}
            )
        ]
        
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool"""
        if name == "echo":
            message = arguments.get("message", "")
            return f"Echo: {message}"
            
        elif name == "get_time":
            return {
                "time": datetime.utcnow().isoformat(),
                "timezone": "UTC"
            }
            
        else:
            raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run example server"""
    server = ExampleMCPServer()
    await server.run()


if __name__ == "__main__":
    # Example usage
    asyncio.run(main())