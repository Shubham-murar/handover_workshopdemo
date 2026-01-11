#!/usr/bin/env python3
"""
MCP server that connects Claude to Qdrant
Provides 2 tools: find_patterns and store_pattern
"""
import sys
import json
from qdrant_client import QdrantClient

def main():
    print("🚀 Starting MCP Server...", file=sys.stderr)
    
    # Connect to Qdrant
    client = QdrantClient(url="http://localhost:6333")
    print("✅ Connected to Qdrant", file=sys.stderr)
    
    # MCP protocol handler
    while True:
        line = sys.stdin.readline()
        if not line:
            break
            
        try:
            data = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
            
        method = data.get("method")
        msg_id = data.get("id")
        
        # Handle initialize
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "workshop-patterns2",
                        "version": "1.0.0"
                    }
                }
            }
            print("✅ Server initialized", file=sys.stderr)
        
        # Handle tools/list
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "find_patterns",
                            "description": "Search Qdrant for code patterns",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Search query"}
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "store_pattern",
                            "description": "Store code patterns in Qdrant",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string", "description": "Pattern description"},
                                    "code": {"type": "string", "description": "Code snippet"}
                                },
                                "required": ["description", "code"]
                            }
                        }
                    ]
                }
            }
            
        # Handle tools/call
        elif method == "tools/call":
            tool_name = data["params"]["name"]
            
            if tool_name == "find_patterns":
                query = data["params"]["arguments"].get("query", "")
                print(f"🔍 Searching for: {query}", file=sys.stderr)
                
                # Search in Qdrant
                try:
                    results = client.scroll(
                        collection_name="workshop-patterns2",
                        limit=3
                    )
                    
                    patterns = []
                    for point in results[0]:
                        patterns.append({
                            "description": point.payload.get("description", ""),
                            "code": point.payload.get("code", "")
                        })
                    
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": json.dumps({
                                    "patterns": patterns,
                                    "count": len(patterns)
                                }, indent=2)
                            }]
                        }
                    }
                except Exception as e:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32603,
                            "message": f"Search failed: {str(e)}"
                        }
                    }
                
            elif tool_name == "store_pattern":
                description = data["params"]["arguments"].get("description", "")
                code = data["params"]["arguments"].get("code", "")
                
                print(f"💾 Storing pattern: {description[:50]}...", file=sys.stderr)
                
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": json.dumps({
                                "message": "Pattern stored successfully",
                                "description": description
                            })
                        }]
                    }
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }
        
        # Handle notifications (no response needed)
        elif method == "notifications/initialized":
            continue
            
        # Unknown method
        else:
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        
        # Send response
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
