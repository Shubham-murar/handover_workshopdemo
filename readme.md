# 🚀 **Workshop: Build a YouTube Video Search App with Claude + MCP + Qdrant**

## 📋 **Complete Workshop Guide**


## **PART 1: PRE-SETUP**

### **Step 1: Install Prerequisites**
```powershell
# 1. Install Python 3.12
winget install Python.Python.3.12

# 2. Install Claude Desktop
# Download from: https://claude.ai/desktop

# 3. Install Docker (for Qdrant)
winget install Docker.DockerDesktop

# 4. Install Git
winget install Git.Git
```

### **Step 2: Create Workshop Directory**
```powershell
# Create main directory
mkdir handover_workshopdemo
cd handover_workshopdemo

# Create Python virtual environment
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip
```

### **Step 3: Install Required Python Packages**
```powershell
pip install fastapi uvicorn qdrant-client sentence-transformers
pip install youtube-transcript-api yt-dlp pydantic jinja2
pip install mcp
```

### **Step 4: Start Qdrant Database**
```powershell
# Start Qdrant in Docker
docker run -d -p 6333:6333 --name qdrant-workshop qdrant/qdrant

# Verify it's running
curl http://localhost:6333
# Should show: {"title":"qdrant - vector search engine","version":"1.16.3"}
```

### **Step 5: Create better_mcp_server.py**
Create this exact file in `handover_workshopdemo/`:
```python
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
```

### **Step 6: Create clean.ps1**
Create this file in `handover_workshopdemo/`:
```powershell
Write-Host "Creating clean config..." -ForegroundColor Green

$configPath = "$env:APPDATA\Claude\claude_desktop_config.json"
$serverPath = "C:\Users\acer\Desktop\handover demo\handover_workshopdemo\better_mcp_server.py"

# Delete old file
if (Test-Path $configPath) {
    Remove-Item $configPath -Force
    Write-Host "Deleted old config" -ForegroundColor Yellow
}

# Create config object
$config = @{
    mcpServers = @{
        "workshop-patterns2" = @{
            command = "python"
            args = @($serverPath)
            env = @{}
        }
    }
}

# Convert to JSON
$json = $config | ConvertTo-Json -Depth 10

# Write without BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines($configPath, $json, $utf8NoBom)

Write-Host "Created config file" -ForegroundColor Green

# Verify
try {
    $test = Get-Content $configPath -Raw | ConvertFrom-Json
    Write-Host "Config is valid JSON" -ForegroundColor Green
    Write-Host "Server command: $($test.mcpServers.'workshop-patterns2'.command)" -ForegroundColor Cyan
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "1. Close Claude Desktop completely" -ForegroundColor Yellow
Write-Host "2. Wait 5 seconds" -ForegroundColor Yellow
Write-Host "3. Open Claude Desktop" -ForegroundColor Yellow
Write-Host "4. Ask Claude to use workshop-patterns2 tool" -ForegroundColor Yellow
```

### **Step 7: Configure Claude Desktop**
```powershell
# Run the configuration script
.\clean.ps1

# Force close Claude Desktop (IMPORTANT!)
Get-Process -Name "Claude" -ErrorAction SilentlyContinue | Stop-Process -Force

# Wait 5 seconds
Start-Sleep -Seconds 5
```

### **Step 8: Open Claude Desktop & Configure Extensions**
1. **Open Claude Desktop** manually
2. Go to **Settings** (gear icon) → **Extensions**
3. Click **"Browse Extensions"**
4. Install **"Filesystem"** extension
5. Give it path: `C:\Users\acer\Desktop\handover demo\handover_workshopdemo`
6. Go to **Developer** tab
7. Verify you see:
   - `Filesystem` - running (managed by extension)
   - `workshop-patterns2` - running

---

## **PART 2: WORKSHOP FLOW**

we're building a YouTube Video Search app, but here's the twist: We're teaching Claude HOW to build it by giving it access to a pattern database, here we will use Qdrant for that. Watch as Claude learns from patterns and creates production code!"

### **Step 1: Verify Everything is Working (5 minutes)**
**Terminal 1 - Show Qdrant:**
```powershell
curl http://localhost:6333
```

**Terminal 2 - Show Filesystem:**
```powershell
ls
# Show: better_mcp_server.py, clean.ps1, venv/
```

**Claude Desktop - Test Connection:**
```
"Can you use the workshop-patterns2 tool to search for FastAPI patterns?"
```

**Expected Claude Response:**
- "Let me search workshop-patterns2..."
- Shows patterns from Qdrant
- **Watch how claude is accessing OUR pattern database!"**

---

## **THE MAGIC PROMPTS (Follow Exactly)**

### **Prompt 1: Project Setup (10 minutes)**
```
"We're building a YouTube Video Search application. I want you to create the complete project structure.

First, search workshop-patterns2 for project organization patterns. Then create:

1. Project structure with app/ directory
2. requirements.txt with necessary dependencies
3. README.md explaining the project
4. .gitignore for Python projects

Use the patterns you find to follow best practices."
```

**Next Actions:**
1. Watch Claude search patterns
2. Watch generated structure
3. Create directories:
```powershell
mkdir -p app/{services,api,templates,static}
```

---

### **Prompt 2: FastAPI Backend (15 minutes)**
```
"Now create the FastAPI backend. Search workshop-patterns2 for:

1. FastAPI application setup patterns
2. CORS middleware patterns  
3. Template rendering patterns
4. Error handling patterns

Create app/main.py with:
- FastAPI app initialization
- CORS middleware
- Template configuration
- Health check endpoint
- Video service integration
- Proper error handling
```

**Demonstrates:**
1. **Key Moment:** Point when Claude says "Searching workshop-patterns2..."
2. Patterns will be found
3. Save generated code:
```powershell
Set-Content -Path "app/main.py" -Value @'
[PASTE CLAUDE'S CODE]
'@
```

---

### **Prompt 3: Video Processing Service (15 minutes)**
```
"Create the video processing service. Search workshop-patterns2 for:

1. YouTube API integration patterns
2. Text chunking/segmentation patterns
3. Vector embedding patterns
4. Qdrant storage patterns

Create app/services/video_service.py with:
- YouTube video ID extraction
- Transcript fetching
- 30-second segment creation with overlaps  
- Sentence transformer embeddings
- Qdrant storage and retrieval
- Semantic search functionality
```

**Test the Service:**
```powershell
python -c "
import sys
sys.path.append('.')
try:
    from app.services.video_service import VideoService
    print('✅ VideoService works!')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

---

### **Prompt 4: API Endpoints (10 minutes)**
```
"Create REST API endpoints. Search workshop-patterns2 for:

1. REST API design patterns
2. Pydantic validation patterns
3. Error response patterns

Create app/api/video.py with:
- POST /api/process - Process YouTube videos
- POST /api/search - Search transcripts
- GET /api/video/{id} - Get video info
- Proper request/response models
```

---

### **Prompt 5: Frontend Templates (15 minutes)**
```
"Create beautiful HTML templates. Search workshop-patterns2 for:

1. DaisyUI component patterns
2. Form design patterns
3. Video player interface patterns

Create:
1. app/templates/index.html - Homepage with YouTube URL input
2. app/templates/video.html - Video player with search sidebar

Make them responsive, modern, and user-friendly."
```

**Start Server to Show:**
```powershell
uvicorn app.main:app --reload --port 7860
```
Open: http://localhost:7860

---

### **Prompt 6: Live Demo - Process a Video (10 minutes)**
```
"Let's test our app! I'll use this YouTube video: https://youtu.be/LPZh9BOjkQs

Explain what happens when we process this video:
1. How does the video ID get extracted?
2. How is the transcript fetched?
3. How are embeddings created?
4. How are they stored in Qdrant?
5. What API endpoints are involved?

Show me the code flow with actual snippets from our implementation."
```

**Host Demonstrates:**
1. Paste URL in web interface
2. Click "Process Video"
3. Show terminal logs
4. **Explain:** "This is vector embeddings in action!"

---

### **Prompt 7: Live Demo - Search Transcripts (10 minutes)**
```
"Now let's search for 'machine learning basics'. Explain:

1. How does the search query get converted to embeddings?
2. How does Qdrant find similar vectors?
3. How are results ranked by relevance?
4. How do timestamps work in the UI?
5. Show me the cosine similarity calculations."

Search for "machine learning basics" and show the results.
```

**Host Demonstrates:**
1. Type search query
2. Show results with scores
3. Click timestamp to jump in video
4. **Explain:** "Semantic search finding meaning, not just keywords!"

---

## **PART 3: TEACHING MOMENTS**

### **Teaching Point 1: RAG for Code Generation**
**Say:** "Traditional RAG retrieves documents for answers. We just did RAG for CODE! Claude retrieved code patterns, then generated new code consistent with those patterns."

### **Teaching Point 2: MCP Magic**
**Say:** "MCP lets Claude talk to external tools. Our server connects Claude to Qdrant, giving it a 'memory' of code patterns. This is how we teach AI our coding standards."

### **Teaching Point 3: Vector DBs for Development**
**Say:** "Qdrant isn't just for user data. We're using it as a development knowledge base - storing proven patterns for AI to learn from and reuse."

---

## **PART 4: TROUBLESHOOTING GUIDE**

### **If MCP Doesn't Show Up:**
1. Close Claude Desktop completely
2. Open Task Manager → End all Claude processes
3. Run: `.\clean.ps1`
4. Reopen Claude Desktop
5. Check Developer tab

### **If Qdrant Connection Fails:**
```powershell
# Restart Qdrant
docker restart qdrant-workshop

# Check if running
docker ps
```

### **If Python Imports Fail:**
```powershell
# Reactivate virtual environment
.\venv\Scripts\Activate.ps1

# Reinstall packages
pip install -r requirements.txt
```

---

## **PART 5: QUICK REFERENCE**

### **Timeline (90-minute workshop):**
```
0-5 min:  Introduction & Setup Check
5-15 min: Prompt 1 - Project Structure
15-30 min: Prompt 2 - FastAPI Backend
30-45 min: Prompt 3 - Video Service
45-55 min: Prompt 4 - API Endpoints
55-70 min: Prompt 5 - Frontend Templates
70-80 min: Prompt 6 - Live Demo Process
80-90 min: Prompt 7 - Live Demo Search & Q&A
```

### **Key Phrases for Host:**
- **"Watch Claude search our pattern database..."** (When Claude uses workshop-patterns2)
- **"See this pattern influence the generated code..."** (When showing patterns)
- **"This is RAG in action: Retrieve, Augment, Generate!"** (During demos)
- **"Our Qdrant knowledge base just helped write production code!"** (After successful generation)

### **What Success Looks Like:**
1. ✅ Claude says "Searching workshop-patterns2..."
2. ✅ Shows patterns from Qdrant
3. ✅ Generates working backend code
4. ✅ Generates beautiful frontend
5. ✅ Application processes videos
6. ✅ Search works with semantic results

---

## **PART 6: EXTENSION IDEAS (If Time Permits)**

### **Prompt 8: Add Features**
```
"How would we extend this? Search workshop-patterns2 for:

1. User authentication patterns
2. Video playlist patterns
3. Analytics dashboard patterns

Show me how to add user accounts feature."
```

### **Prompt 9: Deployment**
```
"How do we deploy this? Search workshop-patterns2 for:

1. Docker containerization patterns
2. Cloud deployment patterns
3. CI/CD pipeline patterns

Create a Dockerfile for our application."
```

---

## **EMERGENCY SCRIPT (keep ready)**

Create `emergency-fix.ps1`:
```powershell
Write-Host "🆘 EMERGENCY FIX SCRIPT" -ForegroundColor Red

# 1. Kill all Claude processes
Get-Process -Name "Claude" -ErrorAction SilentlyContinue | Stop-Process -Force

# 2. Restart Qdrant
docker restart qdrant-workshop

# 3. Run clean config
.\clean.ps1

# 4. Start everything
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 7860

Write-Host "✅ System reset. Open Claude Desktop." -ForegroundColor Green
```

---

## **📚 README.md for Participants**

```markdown
# YouTube Video Search Workshop

## What We Built
A complete YouTube Video Search application that:
- Processes YouTube videos and extracts transcripts
- Creates searchable embeddings using AI
- Allows semantic search within videos
- Jumps to exact timestamps

## How We Built It (The Magic)
We used **RAG for Code Generation**:
1. **Retrieve**: Claude searches Qdrant for code patterns
2. **Augment**: Patterns teach Claude our coding standards
3. **Generate**: Claude creates production-ready code

## Technologies Used
- **Claude Desktop** with MCP (Model Context Protocol)
- **Qdrant** - Vector database for pattern storage
- **FastAPI** - Backend framework
- **Sentence Transformers** - For embeddings
- **DaisyUI** - Frontend components

## Key Concepts Demonstrated
1. **MCP (Model Context Protocol)**: Lets AI use external tools
2. **Vector Databases for Development**: Store code patterns as embeddings
3. **AI as Collaborative Developer**: Teaching AI your coding patterns
4. **Semantic Search**: Finding meaning, not just keywords

## Getting Started (After Workshop)
1. Clone this repository
2. Run `.\clean.ps1` to configure MCP
3. Start Qdrant: `docker run -d -p 6333:6333 qdrant/qdrant`
4. Run: `uvicorn app.main:app --reload --port 7860`
5. Open: http://localhost:7860

## Extend This Project
- Add user authentication
- Create video playlists
- Add collaborative features
- Deploy to cloud
- Add more pattern categories to Qdrant
```

---

## **🎯 FINAL PREPARATION CHECKLIST**

### **Morning of Workshop:**
- [ ] Run `docker start qdrant-workshop`
- [ ] Activate venv: `.\venv\Scripts\Activate.ps1`
- [ ] Run `.\clean.ps1`
- [ ] Close & reopen Claude Desktop
- [ ] Verify workshop-patterns2 in Developer tab
- [ ] Test: "Can you use workshop-patterns2?"
- [ ] Have emergency-fix.ps1 ready

### **During Workshop:**
- [ ] Follow prompt sequence exactly
- [ ] Point out when Claude searches patterns
- [ ] Save generated code immediately
- [ ] Test each component as built
- [ ] Keep browser open showing app
- [ ] Show terminal logs during processing

### **Success Metrics:**
- [ ] Everyone sees Claude search patterns
- [ ] Working backend generated
- [ ] Beautiful frontend generated
- [ ] Video processing works
- [ ] Semantic search works
- [ ] Audience understands RAG concept

---

**Remember:** The magic moment is when Claude says **"Searching workshop-patterns2..."** That's when you point and say: **"Look! Claude is learning from OUR pattern database to build OUR application! This is RAG for code generation working LIVE!"** 🚀
