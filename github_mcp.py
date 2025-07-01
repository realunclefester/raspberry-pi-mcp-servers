#!/usr/bin/env python3
"""GitHub MCP Server

Provides GitHub API operations via MCP protocol.
"""

import asyncio
import json
import os
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from base_server import BaseMCPServer
from mcp.types import Tool


class GitHubMCPServer(BaseMCPServer):
    """GitHub MCP server implementation"""
    
    def __init__(self):
        super().__init__("github", "1.0.0")
        
        # Load GitHub token from environment
        self._load_env()
        
        self.token = os.getenv('GH_TOKEN')
        if not self.token:
            raise ValueError("GH_TOKEN environment variable is required")
            
        self.base_url = "https://api.github.com"
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-MCP-Server/1.0.0'
        }
        
        self.logger.info("GitHub MCP server initialized")
        
    def _load_env(self):
        """Load environment variables from .env file"""
        env_path = Path('/home/rpi/.env')
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"\'')
                        os.environ[key] = value
        
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GitHub API request"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            
            if response.status_code == 204:  # No content
                return {"success": True}
                
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"GitHub API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    raise Exception(f"GitHub API error: {error_data.get('message', str(e))}")
                except:
                    raise Exception(f"GitHub API error: {e}")
            raise Exception(f"GitHub API request failed: {e}")
    
    def get_tools(self) -> List[Tool]:
        """Get available GitHub tools"""
        return [
            self.create_tool(
                name="github_list_repos",
                description="List user's GitHub repositories",
                parameters={
                    "type": {
                        "type": "string",
                        "enum": ["all", "owner", "public", "private", "member"],
                        "description": "Repository type filter",
                        "default": "all"
                    },
                    "sort": {
                        "type": "string", 
                        "enum": ["created", "updated", "pushed", "full_name"],
                        "description": "Sort repositories by",
                        "default": "updated"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of repositories to return",
                        "default": 30
                    }
                }
            ),
            
            self.create_tool(
                name="github_get_repo",
                description="Get detailed information about a repository",
                parameters={
                    "owner": {
                        "type": "string",
                        "description": "Repository owner username"
                    },
                    "repo": {
                        "type": "string", 
                        "description": "Repository name"
                    }
                },
                required=["owner", "repo"]
            ),
            
            self.create_tool(
                name="github_create_repo",
                description="Create a new GitHub repository",
                parameters={
                    "name": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Repository description"
                    },
                    "private": {
                        "type": "boolean",
                        "description": "Whether the repository should be private",
                        "default": False
                    },
                    "auto_init": {
                        "type": "boolean", 
                        "description": "Whether to initialize with README",
                        "default": True
                    }
                },
                required=["name"]
            ),
            
            self.create_tool(
                name="github_list_issues",
                description="List issues for a repository",
                parameters={
                    "owner": {
                        "type": "string",
                        "description": "Repository owner username"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Issue state filter",
                        "default": "open"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of issues to return",
                        "default": 30
                    }
                },
                required=["owner", "repo"]
            ),
            
            self.create_tool(
                name="github_create_issue",
                description="Create a new issue in a repository",
                parameters={
                    "owner": {
                        "type": "string",
                        "description": "Repository owner username"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "title": {
                        "type": "string",
                        "description": "Issue title"
                    },
                    "body": {
                        "type": "string",
                        "description": "Issue body content"
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Issue labels"
                    }
                },
                required=["owner", "repo", "title"]
            ),
            
            self.create_tool(
                name="github_create_pr",
                description="Create a new pull request",
                parameters={
                    "owner": {
                        "type": "string",
                        "description": "Repository owner username"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "title": {
                        "type": "string",
                        "description": "Pull request title"
                    },
                    "body": {
                        "type": "string",
                        "description": "Pull request body content"
                    },
                    "head": {
                        "type": "string",
                        "description": "Branch containing changes"
                    },
                    "base": {
                        "type": "string",
                        "description": "Base branch to merge into",
                        "default": "main"
                    }
                },
                required=["owner", "repo", "title", "head"]
            ),
            
            self.create_tool(
                name="github_get_user",
                description="Get authenticated user information",
                parameters={}
            )
        ]
    
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a GitHub tool"""
        
        if name == "github_list_repos":
            repo_type = arguments.get("type", "all")
            sort = arguments.get("sort", "updated")
            limit = arguments.get("limit", 30)
            
            params = {
                "type": repo_type,
                "sort": sort,
                "per_page": min(limit, 100)
            }
            
            repos = self._make_request("GET", f"/user/repos", data=params)
            
            # Format response
            result = []
            for repo in repos[:limit]:
                result.append({
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "private": repo["private"],
                    "description": repo.get("description"),
                    "url": repo["html_url"],
                    "clone_url": repo["clone_url"],
                    "ssh_url": repo["ssh_url"],
                    "created_at": repo["created_at"],
                    "updated_at": repo["updated_at"],
                    "language": repo.get("language"),
                    "stars": repo["stargazers_count"],
                    "forks": repo["forks_count"]
                })
            
            return {
                "repositories": result,
                "count": len(result)
            }
            
        elif name == "github_get_repo":
            owner = arguments["owner"]
            repo = arguments["repo"]
            
            repo_data = self._make_request("GET", f"/repos/{owner}/{repo}")
            
            return {
                "name": repo_data["name"],
                "full_name": repo_data["full_name"],
                "private": repo_data["private"],
                "description": repo_data.get("description"),
                "url": repo_data["html_url"],
                "clone_url": repo_data["clone_url"],
                "ssh_url": repo_data["ssh_url"],
                "created_at": repo_data["created_at"],
                "updated_at": repo_data["updated_at"],
                "language": repo_data.get("language"),
                "stars": repo_data["stargazers_count"],
                "forks": repo_data["forks_count"],
                "open_issues": repo_data["open_issues_count"],
                "default_branch": repo_data["default_branch"]
            }
            
        elif name == "github_create_repo":
            data = {
                "name": arguments["name"],
                "description": arguments.get("description", ""),
                "private": arguments.get("private", False),
                "auto_init": arguments.get("auto_init", True)
            }
            
            repo = self._make_request("POST", "/user/repos", data=data)
            
            return {
                "name": repo["name"],
                "full_name": repo["full_name"],
                "url": repo["html_url"],
                "clone_url": repo["clone_url"],
                "ssh_url": repo["ssh_url"],
                "private": repo["private"]
            }
            
        elif name == "github_list_issues":
            owner = arguments["owner"]
            repo = arguments["repo"]
            state = arguments.get("state", "open")
            limit = arguments.get("limit", 30)
            
            issues = self._make_request("GET", f"/repos/{owner}/{repo}/issues?state={state}&per_page={min(limit, 100)}")
            
            result = []
            for issue in issues[:limit]:
                # Skip pull requests (they appear in issues API)
                if "pull_request" in issue:
                    continue
                    
                result.append({
                    "number": issue["number"],
                    "title": issue["title"],
                    "body": issue.get("body", ""),
                    "state": issue["state"],
                    "user": issue["user"]["login"],
                    "labels": [label["name"] for label in issue.get("labels", [])],
                    "created_at": issue["created_at"],
                    "updated_at": issue["updated_at"],
                    "url": issue["html_url"]
                })
            
            return {
                "issues": result,
                "count": len(result)
            }
            
        elif name == "github_create_issue":
            owner = arguments["owner"]
            repo = arguments["repo"]
            
            data = {
                "title": arguments["title"],
                "body": arguments.get("body", ""),
                "labels": arguments.get("labels", [])
            }
            
            issue = self._make_request("POST", f"/repos/{owner}/{repo}/issues", data=data)
            
            return {
                "number": issue["number"],
                "title": issue["title"],
                "url": issue["html_url"],
                "state": issue["state"]
            }
            
        elif name == "github_create_pr":
            owner = arguments["owner"]
            repo = arguments["repo"]
            
            data = {
                "title": arguments["title"],
                "body": arguments.get("body", ""),
                "head": arguments["head"],
                "base": arguments.get("base", "main")
            }
            
            pr = self._make_request("POST", f"/repos/{owner}/{repo}/pulls", data=data) 
            
            return {
                "number": pr["number"],
                "title": pr["title"],
                "url": pr["html_url"],
                "state": pr["state"]
            }
            
        elif name == "github_get_user":
            user = self._make_request("GET", "/user")
            
            return {
                "login": user["login"],
                "name": user.get("name"),
                "email": user.get("email"),
                "bio": user.get("bio"),
                "public_repos": user["public_repos"],
                "followers": user["followers"],
                "following": user["following"],
                "created_at": user["created_at"],
                "url": user["html_url"]
            }
            
        else:
            raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run GitHub MCP server"""
    server = GitHubMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())