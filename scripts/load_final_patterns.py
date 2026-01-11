import sys
from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid

print("?? Loading patterns for workshop...")

try:
    # Connect to Qdrant
    client = QdrantClient(host="localhost", port=6333)
    
    # Check connection
    client.get_collections()
    print("? Connected to Qdrant")
    
    # Collection name
    COLLECTION_NAME = "workshop-patterns2"
    
    # Delete old collection if exists
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        print(f"? Cleared old collection")
    except:
        pass
    
    # Create new collection
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
    )
    print(f"? Created collection: {COLLECTION_NAME}")
    
    # Define patterns
    patterns = [
        {
            "description": "FastAPI setup with CORS middleware",
            "category": "backend",
            "code": "from fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\n\napp = FastAPI(title='YouTube Video Search')\n\napp.add_middleware(\n    CORSMiddleware,\n    allow_origins=['*'],\n    allow_credentials=True,\n    allow_methods=['*'],\n    allow_headers=['*'],\n)\n\n@app.get('/')\ndef home():\n    return {'message': 'Welcome to YouTube Video Search API'}"
        },
        {
            "description": "DaisyUI card with form for YouTube URL",
            "category": "frontend",
            "code": "<div class='card bg-base-100 shadow-xl'>\n  <div class='card-body'>\n    <h2 class='card-title'>YouTube Video Search</h2>\n    <form>\n      <input type='url' placeholder='YouTube URL' class='input input-bordered'>\n      <button class='btn btn-primary'>Search</button>\n    </form>\n  </div>\n</div>"
        },
        {
            "description": "YouTube video ID extraction function",
            "category": "youtube",
            "code": "import re\n\ndef extract_video_id(url):\n    patterns = [\n        r'v=([\\w-]+)',\n        r'youtu.be/([\\w-]+)',\n        r'embed/([\\w-]+)'\n    ]\n    for pattern in patterns:\n        match = re.search(pattern, url)\n        if match:\n            return match.group(1)\n    return url"
        }
    ]
    
    # Add patterns to Qdrant
    points = []
    for i, pattern in enumerate(patterns):
        point = models.PointStruct(
            id=str(uuid.uuid4()),
            vector=[float(i)/10.0] * 384,  # Simple vector
            payload=pattern
        )
        points.append(point)
    
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"? Loaded {len(patterns)} patterns into Qdrant")
    
    # Verify
    count = client.count(collection_name=COLLECTION_NAME)
    print(f"Total patterns: {count.count}")
    
    print("\n?? Patterns ready for workshop!")
    
except Exception as e:
    print(f"? Error: {e}")
    print("\nMake sure Qdrant is running:")
    print("  docker run -d -p 6333:6333 qdrant/qdrant")
    sys.exit(1)


