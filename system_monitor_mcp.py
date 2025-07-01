#!/usr/bin/env python3
"""System Monitor MCP Server

Provides system monitoring capabilities via MCP protocol.
"""

import asyncio
import json
import psutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Dict, List, Any

from mcp.server import Server
from mcp.types import Tool, TextContent


# Create server instance
server = Server("system-monitor")

# Watchdog configuration
WATCHDOG_CONFIG = {
    'cpu_threshold': 85.0,      # %
    'memory_threshold': 80.0,   # %
    'disk_threshold': 90.0,     # %
    'temp_threshold': 70.0,     # °C
    'check_interval': 30,       # seconds
    'enabled': True
}

# Global watchdog state
watchdog_running = False
watchdog_thread = None


def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status"""
    try:
        # CPU info
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory info
        memory = psutil.virtual_memory()
        
        # Disk info
        disk = psutil.disk_usage('/')
        
        # Network info
        network = psutil.net_io_counters()
        
        # Temperature (RPi specific)
        try:
            temp_result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                       capture_output=True, text=True)
            temperature = temp_result.stdout.strip().replace('temp=', '').replace("'", '')
        except:
            temperature = 'N/A'
        
        # Load average
        load_avg = subprocess.run(['uptime'], capture_output=True, text=True).stdout.strip()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu': {
                'usage_percent': cpu_percent,
                'cores': cpu_count
            },
            'memory': {
                'total_gb': round(memory.total / (1024**3), 2),
                'used_gb': round(memory.used / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2),
                'percent': memory.percent
            },
            'disk': {
                'total_gb': round(disk.total / (1024**3), 2),
                'used_gb': round(disk.used / (1024**3), 2),
                'free_gb': round(disk.free / (1024**3), 2),
                'percent': round((disk.used / disk.total) * 100, 1)
            },
            'network': {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv
            },
            'temperature': temperature,
            'load_average': load_avg
        }
    except Exception as e:
        return {'error': str(e)}


def get_processes(limit: int = 10) -> List[Dict[str, Any]]:
    """Get list of running processes sorted by CPU usage"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(proc.info)
        except psutil.NoSuchProcess:
            continue
    
    # Sort by CPU usage
    processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
    
    return processes[:limit]


def check_service_health() -> Dict[str, bool]:
    """Check health of critical services"""
    services = {}
    
    # Check Docker
    try:
        result = subprocess.run(['docker', 'ps'], capture_output=True, timeout=5)
        services['docker'] = result.returncode == 0
    except:
        services['docker'] = False
    
    # Check Qdrant
    try:
        import urllib.request
        response = urllib.request.urlopen('http://localhost:6333/healthz', timeout=5)
        services['qdrant'] = response.getcode() == 200
    except:
        services['qdrant'] = False
    
    # Check PostgreSQL (via Docker)
    try:
        result = subprocess.run(['docker', 'exec', 'postgres', 'pg_isready', '-U', 'postgres'], 
                              capture_output=True, timeout=5)
        services['postgresql'] = result.returncode == 0
    except:
        services['postgresql'] = False
    
    # Check Embeddings service
    try:
        import urllib.request
        response = urllib.request.urlopen('http://localhost:8001/health', timeout=5)
        services['embeddings'] = response.getcode() == 200
    except:
        services['embeddings'] = False
    
    return services


def alert_to_stderr(message: str, level: str = "WARNING"):
    """Send alert to stderr for Claude Code to see"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    alert = f"[{timestamp}] {level}: {message}"
    print(alert, file=sys.stderr, flush=True)


def watchdog_check():
    """Perform watchdog checks and alert on issues"""
    try:
        # Resource checks
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        
        # Temperature check (RPi specific)
        temp_celsius = None
        try:
            temp_result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                       capture_output=True, text=True, timeout=5)
            temp_str = temp_result.stdout.strip().replace('temp=', '').replace("'", '')
            if temp_str.endswith('C'):
                temp_celsius = float(temp_str[:-1])
        except:
            pass
        
        # Check thresholds
        if cpu_percent > WATCHDOG_CONFIG['cpu_threshold']:
            alert_to_stderr(f"High CPU usage: {cpu_percent:.1f}%", "WARNING")
        
        if memory_percent > WATCHDOG_CONFIG['memory_threshold']:
            alert_to_stderr(f"High memory usage: {memory_percent:.1f}%", "WARNING")
        
        if disk_percent > WATCHDOG_CONFIG['disk_threshold']:
            alert_to_stderr(f"High disk usage: {disk_percent:.1f}%", "WARNING")
        
        if temp_celsius and temp_celsius > WATCHDOG_CONFIG['temp_threshold']:
            alert_to_stderr(f"High temperature: {temp_celsius:.1f}°C", "WARNING")
        
        # Service checks
        services = check_service_health()
        for service_name, is_healthy in services.items():
            if not is_healthy:
                alert_to_stderr(f"Service {service_name} is down or unreachable", "ERROR")
    
    except Exception as e:
        alert_to_stderr(f"Watchdog check failed: {str(e)}", "ERROR")


def watchdog_loop():
    """Background watchdog monitoring loop"""
    global watchdog_running
    
    alert_to_stderr("System watchdog started", "INFO")
    
    while watchdog_running and WATCHDOG_CONFIG['enabled']:
        try:
            watchdog_check()
            time.sleep(WATCHDOG_CONFIG['check_interval'])
        except Exception as e:
            alert_to_stderr(f"Watchdog loop error: {str(e)}", "ERROR")
            time.sleep(WATCHDOG_CONFIG['check_interval'])
    
    alert_to_stderr("System watchdog stopped", "INFO")


def start_watchdog():
    """Start the background watchdog"""
    global watchdog_running, watchdog_thread
    
    if not watchdog_running and WATCHDOG_CONFIG['enabled']:
        watchdog_running = True
        watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
        watchdog_thread.start()
        return True
    return False


def stop_watchdog():
    """Stop the background watchdog"""
    global watchdog_running
    watchdog_running = False
    return True


def get_watchdog_status() -> Dict[str, Any]:
    """Get current watchdog status and configuration"""
    return {
        'running': watchdog_running,
        'config': WATCHDOG_CONFIG,
        'thread_alive': watchdog_thread.is_alive() if watchdog_thread else False
    }


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="get_system_status",
            description="Get comprehensive system status including CPU, memory, disk, network and temperature",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_processes",
            description="Get list of running processes sorted by CPU usage",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of processes to return",
                        "default": 10
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_memory_details",
            description="Get detailed memory usage information",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_disk_usage",
            description="Get disk usage for all mounted filesystems",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_network_connections",
            description="Get active network connections",
            inputSchema={
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "description": "Connection type filter: inet, inet4, inet6, tcp, tcp4, tcp6, udp, udp4, udp6",
                        "default": "inet"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="start_watchdog",
            description="Start the system watchdog for continuous monitoring",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="stop_watchdog",
            description="Stop the system watchdog",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_watchdog_status",
            description="Get current watchdog status and configuration",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="check_service_health",
            description="Check health status of critical services",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    if name == "get_system_status":
        status = get_system_status()
        return [TextContent(
            type="text",
            text=json.dumps(status, indent=2)
        )]
    
    elif name == "get_processes":
        limit = arguments.get("limit", 10)
        processes = get_processes(limit)
        return [TextContent(
            type="text",
            text=json.dumps(processes, indent=2)
        )]
    
    elif name == "get_memory_details":
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        details = {
            "virtual_memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used,
                "free": memory.free,
                "active": getattr(memory, 'active', None),
                "inactive": getattr(memory, 'inactive', None),
                "buffers": getattr(memory, 'buffers', None),
                "cached": getattr(memory, 'cached', None),
                "shared": getattr(memory, 'shared', None)
            },
            "swap_memory": {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": swap.percent,
                "sin": swap.sin,
                "sout": swap.sout
            }
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(details, indent=2)
        )]
    
    elif name == "get_disk_usage":
        partitions = psutil.disk_partitions()
        disk_info = []
        
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent": usage.percent
                })
            except PermissionError:
                continue
        
        return [TextContent(
            type="text",
            text=json.dumps(disk_info, indent=2)
        )]
    
    elif name == "get_network_connections":
        kind = arguments.get("kind", "inet")
        connections = psutil.net_connections(kind=kind)
        
        conn_info = []
        for conn in connections:
            conn_info.append({
                "fd": conn.fd,
                "family": str(conn.family),
                "type": str(conn.type),
                "laddr": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                "raddr": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                "status": conn.status if hasattr(conn, 'status') else None,
                "pid": conn.pid
            })
        
        return [TextContent(
            type="text",
            text=json.dumps(conn_info, indent=2)
        )]
    
    elif name == "start_watchdog":
        success = start_watchdog()
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": success,
                "message": "Watchdog started" if success else "Watchdog already running or disabled"
            }, indent=2)
        )]
    
    elif name == "stop_watchdog":
        success = stop_watchdog()
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": success,
                "message": "Watchdog stopped" if success else "Watchdog was not running"
            }, indent=2)
        )]
    
    elif name == "get_watchdog_status":
        status = get_watchdog_status()
        return [TextContent(
            type="text",
            text=json.dumps(status, indent=2)
        )]
    
    elif name == "check_service_health":
        services = check_service_health()
        return [TextContent(
            type="text",
            text=json.dumps(services, indent=2)
        )]
    
    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


async def main():
    """Run the MCP server using stdio transport"""
    from mcp import stdio_server
    
    # Auto-start watchdog on server start
    if WATCHDOG_CONFIG['enabled']:
        start_watchdog()
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream=read_stream,
                write_stream=write_stream,
                initialization_options=server.create_initialization_options()
            )
    finally:
        # Cleanup on exit
        stop_watchdog()


if __name__ == "__main__":
    asyncio.run(main())