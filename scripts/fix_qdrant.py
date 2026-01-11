from qdrant_client import QdrantClient

# Try different connection methods
try:
    # Method 1: Using host and port
    client = QdrantClient(host="localhost", port=6333)
    print("? Connected using host='localhost', port=6333")
except Exception as e1:
    print(f"? Method 1 failed: {e1}")
    try:
        # Method 2: Using URL
        client = QdrantClient(url="http://localhost:6333")
        print("? Connected using url='http://localhost:6333'")
    except Exception as e2:
        print(f"? Method 2 failed: {e2}")
        try:
            # Method 3: Just location
            client = QdrantClient(location=":memory:")  # For testing
            print("?? Using in-memory Qdrant for demo")
        except Exception as e3:
            print(f"? All methods failed: {e3}")
            client = None

if client:
    # Check collections
    collections = client.get_collections()
    print(f"Found collections: {[c.name for c in collections.collections]}")



