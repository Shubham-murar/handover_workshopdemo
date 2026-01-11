import json
from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid
import hashlib

print("Connecting to LOCAL Qdrant at localhost:6333...")
client = QdrantClient(host="localhost", port=6333)

# Collection name
COLLECTION_NAME = "workshop-patterns2"

# Delete if exists (for clean start)
try:
    client.delete_collection(collection_name=COLLECTION_NAME)
    print(f"Deleted existing collection '{COLLECTION_NAME}'")
except:
    pass

# Create fresh collection
client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
)
print(f"Created collection '{COLLECTION_NAME}'")

# Define patterns with SIMPLER strings (no complex quotes)
patterns = [
    {
        "description": "FastAPI application setup with CORS for web applications",
        "category": "fastapi",
        "code": "from fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\nfrom fastapi.staticfiles import StaticFiles\nfrom fastapi.templating import Jinja2Templates\n\napp = FastAPI(title='YouTube Video Search')\n\n# Enable CORS for frontend\napp.add_middleware(\n    CORSMiddleware,\n    allow_origins=['*'],\n    allow_credentials=True,\n    allow_methods=['*'],\n    allow_headers=['*'],\n)\n\n# Setup templates\ntemplates = Jinja2Templates(directory='templates')\n\n@app.get('/')\nasync def home():\n    return {'message': 'Welcome to YouTube Video Search API'}"
    },
    {
        "description": "DaisyUI homepage with form for YouTube URL input",
        "category": "frontend", 
        "code": "<!DOCTYPE html>\n<html data-theme='light'>\n<head>\n    <meta charset='UTF-8'>\n    <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n    <title>YouTube Video Search</title>\n    <link href='https://cdn.jsdelivr.net/npm/daisyui@3.x/dist/full.css' rel='stylesheet'>\n    <script src='https://cdn.tailwindcss.com'></script>\n</head>\n<body class='min-h-screen bg-base-200'>\n    <div class='container mx-auto p-8'>\n        <div class='card bg-base-100 shadow-xl max-w-2xl mx-auto'>\n            <div class='card-body'>\n                <h1 class='card-title text-3xl mb-6'>🎬 YouTube Video Search</h1>\n                <p class='mb-6'>Paste a YouTube URL to search through its transcript</p>\n                \n                <form id='videoForm' class='space-y-4'>\n                    <input \n                        type='url' \n                        placeholder='https://www.youtube.com/watch?v=...' \n                        class='input input-bordered w-full'\n                        id='youtubeUrl'\n                        required>\n                    \n                    <button type='submit' class='btn btn-primary w-full'>\n                        Process Video\n                    </button>\n                </form>\n                \n                <div id='result' class='mt-6 hidden'>\n                    <!-- Results will appear here -->\n                </div>\n            </div>\n        </div>\n    </div>\n    \n    <script>\n    document.getElementById('videoForm').addEventListener('submit', async (e) => {\n        e.preventDefault();\n        const url = document.getElementById('youtubeUrl').value;\n        // API call will be added later\n        alert('Processing: ' + url);\n    });\n    </script>\n</body>\n</html>"
    },
    {
        "description": "YouTube video ID extraction function with regex patterns",
        "category": "youtube",
        "code": "import re\n\ndef extract_video_id(youtube_url: str) -> str:\n    patterns = [\n        r'(?:youtube\\\\.com/watch\\\\?v=|youtu\\\\.be/)([\\\\w-]+)',\n        r'(?:youtube\\\\.com/embed/)([\\\\w-]+)',\n        r'(?:youtube\\\\.com/v/)([\\\\w-]+)',\n        r'(?:youtube\\\\.com/shorts/)([\\\\w-]+)',\n    ]\n    \n    for pattern in patterns:\n        match = re.search(pattern, youtube_url)\n        if match:\n            return match.group(1)\n    \n    # If no pattern matches, assume input is already a video ID\n    if re.match(r'^[\\\\w-]+$', youtube_url):\n        return youtube_url\n    \n    raise ValueError(f'Could not extract video ID from URL: {youtube_url}')"
    },
    {
        "description": "FastAPI video processing endpoint with error handling",
        "category": "fastapi",
        "code": "from fastapi import APIRouter, HTTPException\nfrom pydantic import BaseModel\nfrom typing import Optional\n\nrouter = APIRouter()\n\nclass VideoRequest(BaseModel):\n    url: str\n\nclass VideoResponse(BaseModel):\n    video_id: str\n    title: Optional[str] = None\n    success: bool\n    message: str\n\n@router.post('/process', response_model=VideoResponse)\nasync def process_video(request: VideoRequest):\n    try:\n        # Extract video ID\n        from .services.video_service import extract_video_id\n        video_id = extract_video_id(request.url)\n        \n        return VideoResponse(\n            video_id=video_id,\n            title=f'Video {video_id}',\n            success=True,\n            message='Video processing started'\n        )\n    except Exception as e:\n        raise HTTPException(\n            status_code=500,\n            detail=f'Failed to process video: {str(e)}'\n        )"
    },
    {
        "description": "Video service with transcript processing and embeddings",
        "category": "service",
        "code": "import logging\nfrom typing import List, Dict, Any\nfrom sentence_transformers import SentenceTransformer\n\nclass VideoService:\n    def __init__(self):\n        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')\n        self.logger = logging.getLogger(__name__)\n    \n    def get_embeddings(self, text: str) -> List[float]:\n        return self.model.encode(text).tolist()\n    \n    def create_segments(self, transcript: List[Dict], chunk_size: int = 30, overlap: int = 10):\n        segments = []\n        \n        for i in range(0, len(transcript), chunk_size - overlap):\n            end_idx = min(i + chunk_size, len(transcript))\n            segment_text = ' '.join([t['text'] for t in transcript[i:end_idx]])\n            \n            if segment_text:\n                segments.append({\n                    'text': segment_text,\n                    'start': transcript[i]['start'],\n                    'end': transcript[end_idx-1]['start'] + transcript[end_idx-1]['duration'],\n                    'index': len(segments)\n                })\n        \n        return segments\n    \n    def process_transcript(self, transcript: List[Dict]) -> List[Dict]:\n        segments = self.create_segments(transcript)\n        \n        for segment in segments:\n            segment['embedding'] = self.get_embeddings(segment['text'])\n        \n        return segments"
    }
]

print(f"Loading {len(patterns)} patterns into Qdrant...")

# Upload patterns to Qdrant
points = []
for pattern in patterns:
    # Create simple embedding from hash of description
    text = pattern["description"] + pattern["category"]
    hash_val = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
    embedding = [(hash_val % 1000) / 1000.0 for _ in range(384)]
    
    point = models.PointStruct(
        id=str(uuid.uuid4()),
        vector=embedding,
        payload={
            "description": pattern["description"],
            "category": pattern["category"],
            "code": pattern["code"],
            "type": "code-pattern"
        }
    )
    points.append(point)

# Upload in one batch
client.upsert(
    collection_name=COLLECTION_NAME,
    points=points
)

print(f"✅ Successfully loaded {len(points)} patterns into LOCAL Qdrant")

# Verify
count_result = client.count(collection_name=COLLECTION_NAME)
print(f"Total patterns in collection: {count_result.count}")

print("\n🎯 Patterns loaded:")
for pattern in patterns:
    print(f"  • {pattern['description']}")

print("\n✅ Done! Ready for workshop.")
