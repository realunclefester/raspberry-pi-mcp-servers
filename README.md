# Raspberry Pi MCP Servers Collection

**Production-ready MCP (Model Context Protocol) servers optimized for Raspberry Pi and AI workloads**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![ARM64 Compatible](https://img.shields.io/badge/ARM64-compatible-green.svg)](https://www.raspberrypi.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🚀 Overview

This collection provides MCP servers specifically designed for AI-powered systems running on Raspberry Pi. These servers enable Claude and other AI assistants to interact with system resources, databases, and external services through a standardized protocol.

### Key Features

- **ARM Optimized**: Designed for efficient operation on Raspberry Pi hardware
- **Production Ready**: Used in 24/7 autonomous AI systems
- **PostgreSQL + pgvector**: Advanced vector storage for AI memory
- **System Monitoring**: Real-time resource tracking
- **Workflow Integration**: Node-RED compatibility

## 📦 Available Servers

### 1. PostgreSQL + pgvector MCP (`postgres_mcp.py`)

Advanced PostgreSQL interface with vector similarity search capabilities.

**Features:**
- Execute SQL queries with parameterized inputs
- Vector similarity search using pgvector
- Table introspection and schema management
- Connection pooling for performance
- ARM-optimized pgvector operations

**Use Cases:**
- AI memory storage and retrieval
- Semantic search across documents
- Time-series data analysis
- Event logging and analytics

### 2. pgvector Memory MCP (`pgvector_memory_mcp.py`)

Persistent memory system for AI assistants using PostgreSQL and pgvector.

**Features:**
- Store and retrieve contextual memories
- Semantic search across memories
- Category-based organization
- Priority levels for memory importance
- Automatic embedding generation

**Use Cases:**
- Long-term context retention
- Knowledge base management
- User preference storage
- Troubleshooting history

### 3. System Monitor MCP (`system_monitor_mcp.py`)

Comprehensive system monitoring for Raspberry Pi.

**Features:**
- CPU, memory, disk, and network statistics
- Temperature monitoring
- Process management
- Service health checks
- Watchdog functionality

**Use Cases:**
- Resource optimization
- Performance monitoring
- Automated system maintenance
- Alert generation

### 4. Node-RED MCP (`node_red_mcp.py`)

Integration with Node-RED for workflow automation.

**Features:**
- Flow management and inspection
- Node search and details
- Context variable access
- Inject node triggering
- Flow analysis and statistics

**Use Cases:**
- Workflow automation
- Event-driven processing
- IoT integrations
- Visual programming interface

### 5. GitHub MCP (`github_mcp.py`)

GitHub operations and repository management.

**Features:**
- Repository listing and creation
- Issue and PR management
- User information retrieval
- Authenticated operations

**Use Cases:**
- Automated repository management
- Issue tracking integration
- Code deployment workflows

## 🛠️ Installation

### Prerequisites

```bash
# Python 3.11+ (comes with Raspberry Pi OS)
python3 --version

# PostgreSQL with pgvector
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
```

### Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/raspberry-pi-mcp-servers.git
cd raspberry-pi-mcp-servers
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

4. Add to Claude configuration (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "postgres": {
      "type": "stdio",
      "command": "python",
      "args": ["/path/to/postgres_mcp.py"]
    },
    "memory": {
      "type": "stdio",
      "command": "python",
      "args": ["/path/to/memory_mcp.py"]
    }
  }
}
```

## 📊 Performance

Optimized for Raspberry Pi 5 (8GB RAM):

| Server | Memory Usage | CPU Impact | Startup Time |
|--------|--------------|------------|--------------|
| PostgreSQL MCP | ~55MB | <1% idle | <1s |
| Memory MCP | ~55MB | <1% idle | <1s |
| System Monitor | ~50MB | 1-2% active | <1s |
| Node-RED MCP | ~55MB | <1% idle | <1s |

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│          Claude / AI Assistant          │
├─────────────────────────────────────────┤
│            MCP Protocol Layer           │
├────────┬────────┬────────┬──────┬──────┤
│Postgres│ Memory │System  │Node- │GitHub│
│  MCP   │  MCP   │Monitor │ RED  │ MCP  │
├────────┴────────┴────────┴──────┴──────┤
│          System Resources               │
│  PostgreSQL | pgvector | Node-RED | OS  │
└─────────────────────────────────────────┘
```

## 🔒 Security

- Environment-based configuration
- No hardcoded credentials
- PostgreSQL connection pooling
- Input validation and sanitization
- Read-only operations by default

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Anthropic's MCP SDK](https://github.com/anthropics/mcp)
- Optimized for [Raspberry Pi](https://www.raspberrypi.com/)
- Uses [pgvector](https://github.com/pgvector/pgvector) for vector operations

---

**Made with ❤️ for the Raspberry Pi AI community**