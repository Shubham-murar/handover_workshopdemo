"""
YouTube Video Processing Service

This module handles YouTube video processing, including:
- Video ID extraction
- Transcript retrieval
- Segment creation with overlapping windows
- Embedding generation
- Vector storage and search using Qdrant
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)
import yt_dlp

from app.services.demo_data import get_demo_transcript, list_demo_videos
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SEGMENT_DURATION = 30  # seconds
OVERLAP_DURATION = 5   # seconds for overlap between segments
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast and efficient model
COLLECTION_NAME = "youtube_segments"
VECTOR_SIZE = 384  # Size for all-MiniLM-L6-v2 model


class VideoServiceError(Exception):
    """Base exception for video service errors"""
    pass


class VideoService:
    """Service for processing YouTube videos and managing embeddings"""
    
    def __init__(self, qdrant_url: str = "localhost", qdrant_port: int = 6333):
        """
        Initialize the video service
        
        Args:
            qdrant_url: Qdrant server URL
            qdrant_port: Qdrant server port
        """
        try:
            # Initialize Qdrant client
            self.qdrant_client = QdrantClient(host=qdrant_url, port=qdrant_port)
            logger.info(f"Connected to Qdrant at {qdrant_url}:{qdrant_port}")
            
            # Initialize embedding model
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
            self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("Embedding model loaded successfully")
            
            # Ensure collection exists
            self._ensure_collection_exists()
            
        except Exception as e:
            logger.error(f"Failed to initialize VideoService: {e}")
            raise VideoServiceError(f"Initialization failed: {e}")
    
    def _ensure_collection_exists(self):
        """Create Qdrant collection if it doesn't exist"""
        try:
            collections = self.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if COLLECTION_NAME not in collection_names:
                logger.info(f"Creating collection: {COLLECTION_NAME}")
                self.qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=VECTOR_SIZE,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Collection {COLLECTION_NAME} created successfully")
            else:
                logger.info(f"Collection {COLLECTION_NAME} already exists")
                
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            raise VideoServiceError(f"Collection setup failed: {e}")
    
    @staticmethod
    def extract_video_id(youtube_url: str) -> str:
        """
        Extract YouTube video ID from various URL formats
        
        Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - https://www.youtube.com/v/VIDEO_ID
        
        Args:
            youtube_url: YouTube URL in any supported format
            
        Returns:
            Video ID as string
            
        Raises:
            VideoServiceError: If URL is invalid or video ID cannot be extracted
        """
        if not youtube_url:
            raise VideoServiceError("URL cannot be empty")
        
        # Pattern for various YouTube URL formats
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                video_id = match.group(1)
                logger.info(f"Extracted video ID: {video_id}")
                return video_id
        
        # Try parsing as URL
        try:
            parsed_url = urlparse(youtube_url)
            if parsed_url.hostname in ['www.youtube.com', 'youtube.com']:
                query_params = parse_qs(parsed_url.query)
                if 'v' in query_params:
                    video_id = query_params['v'][0]
                    logger.info(f"Extracted video ID from query params: {video_id}")
                    return video_id
        except Exception as e:
            logger.warning(f"Failed to parse URL: {e}")
        
        raise VideoServiceError(
            f"Could not extract video ID from URL: {youtube_url}. "
            "Please provide a valid YouTube URL."
        )
    
    def get_transcript(self, video_id: str, use_demo: bool = False) -> List[Dict]:
        """
        Retrieve transcript for a YouTube video
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            List of transcript entries with 'text', 'start', and 'duration'
            
        Raises:
            VideoServiceError: If transcript cannot be retrieved
        """
        try:
            logger.info(f"Fetching transcript for video: {video_id}")
            
            # Check if this is a demo video ID
            if video_id.startswith('DEMO') or use_demo:
                demo_data = get_demo_transcript(video_id)
                if demo_data:
                    logger.info(f"Using demo transcript for {video_id}: {demo_data['title']}")
                    return demo_data['transcript']
                else:
                    raise VideoServiceError(f"Demo video {video_id} not found. Available: LPZh9BOjkQs")
            
            # Try to get transcript in multiple languages
            try:
                # First try English
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            except:
                # If English fails, try auto-generated
                try:
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    transcript = transcript_list.find_generated_transcript(['en']).fetch()
                except:
                    # Try using yt-dlp as fallback
                    try:
                        logger.info("Trying yt-dlp as fallback...")
                        transcript = self._get_transcript_with_ytdlp(video_id)
                    except:
                        # If that fails, try any available transcript
                        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                        available_transcripts = list(transcript_list)
                        if available_transcripts:
                            transcript = available_transcripts[0].fetch()
                        else:
                            raise NoTranscriptFound(video_id)
            
            logger.info(f"Retrieved {len(transcript)} transcript entries")
            return transcript
            
        except TranscriptsDisabled:
            raise VideoServiceError(
                f"Transcripts are disabled for video {video_id}. "
                "Please try a different video with captions enabled."
            )
        except NoTranscriptFound:
            raise VideoServiceError(
                f"No transcript found for video {video_id}. "
                "The video may not have captions/subtitles available. "
                "Please try a different video or enable captions on the video."
            )
        except VideoUnavailable:
            raise VideoServiceError(
                f"Video {video_id} is unavailable or private. "
                "Please check the video URL and try again."
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error fetching transcript: {error_msg}")
            
            # Provide helpful error messages
            if "no element found" in error_msg.lower():
                raise VideoServiceError(
                    f"Failed to fetch transcript for video {video_id}. "
                    "This video may not have captions/subtitles available, "
                    "or YouTube may be blocking automated requests. "
                    "Please try: 1) A video with manual captions, 2) A different video, "
                    "or 3) Wait a few minutes before trying again."
                )
            else:
                raise VideoServiceError(f"Failed to fetch transcript: {error_msg}")
    
    def _get_transcript_with_ytdlp(self, video_id: str) -> List[Dict]:
        """Fallback method using yt-dlp to get subtitles"""
        try:
            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
                'quiet': True,
                'no_warnings': True,
            }
            
            url = f'https://www.youtube.com/watch?v={video_id}'
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Get subtitles
                if 'subtitles' in info and 'en' in info['subtitles']:
                    sub_url = info['subtitles']['en'][0]['url']
                elif 'automatic_captions' in info and 'en' in info['automatic_captions']:
                    sub_url = info['automatic_captions']['en'][0]['url']
                else:
                    raise Exception("No subtitles found")
                
                # Download and parse subtitles
                import urllib.request
                import json
                
                response = urllib.request.urlopen(sub_url)
                subtitle_data = json.loads(response.read())
                
                # Convert to our format
                transcript = []
                if 'events' in subtitle_data:
                    for event in subtitle_data['events']:
                        if 'segs' in event:
                            text = ''.join([seg.get('utf8', '') for seg in event['segs']])
                            if text.strip():
                                transcript.append({
                                    'text': text.strip(),
                                    'start': event.get('tStartMs', 0) / 1000.0,
                                    'duration': event.get('dDurationMs', 0) / 1000.0
                                })
                
                return transcript
                
        except Exception as e:
            logger.error(f"yt-dlp fallback failed: {e}")
            raise
    
    def create_segments(self, transcript: List[Dict]) -> List[Dict]:
        """
        Create overlapping segments from transcript
        
        Segments are created with SEGMENT_DURATION length and OVERLAP_DURATION overlap
        
        Args:
            transcript: List of transcript entries from YouTube
            
        Returns:
            List of segments with 'text', 'start_time', 'end_time', and 'duration'
        """
        if not transcript:
            logger.warning("Empty transcript provided")
            return []
        
        segments = []
        current_segment_start = 0
        
        while current_segment_start < len(transcript):
            # Calculate segment end time
            segment_end_time = transcript[current_segment_start]['start'] + SEGMENT_DURATION
            
            # Collect all transcript entries within this segment
            segment_entries = []
            idx = current_segment_start
            
            while idx < len(transcript):
                entry = transcript[idx]
                entry_end = entry['start'] + entry['duration']
                
                # Include entry if it starts before segment end
                if entry['start'] < segment_end_time:
                    segment_entries.append(entry)
                    idx += 1
                else:
                    break
            
            if not segment_entries:
                break
            
            # Create segment
            segment_text = ' '.join(entry['text'] for entry in segment_entries)
            start_time = segment_entries[0]['start']
            last_entry = segment_entries[-1]
            end_time = min(
                last_entry['start'] + last_entry['duration'],
                start_time + SEGMENT_DURATION
            )
            
            segments.append({
                'text': segment_text,
                'start_time': start_time,
                'end_time': end_time,
                'duration': end_time - start_time
            })
            
            # Move to next segment start (with overlap)
            overlap_time = segment_entries[0]['start'] + (SEGMENT_DURATION - OVERLAP_DURATION)
            
            # Find the next starting position
            next_start = current_segment_start
            for i in range(current_segment_start, len(transcript)):
                if transcript[i]['start'] >= overlap_time:
                    next_start = i
                    break
            else:
                # No more entries
                break
            
            # Prevent infinite loop
            if next_start <= current_segment_start:
                next_start = current_segment_start + 1
            
            current_segment_start = next_start
        
        logger.info(f"Created {len(segments)} segments from transcript")
        return segments
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for texts using sentence-transformers
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        try:
            logger.info(f"Generating embeddings for {len(texts)} texts")
            embeddings = self.embedding_model.encode(
                texts,
                show_progress_bar=len(texts) > 10,
                convert_to_numpy=True
            )
            logger.info("Embeddings generated successfully")
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise VideoServiceError(f"Failed to generate embeddings: {e}")
    
    def store_segments(self, video_id: str, segments: List[Dict], 
                    embeddings: List[List[float]], metadata: Dict = None):
        """
        Store segments and embeddings in Qdrant
        
        Args:
            video_id: YouTube video ID
            segments: List of segment dictionaries
            embeddings: List of embedding vectors
            metadata: Optional metadata to store with all segments
        """
        if len(segments) != len(embeddings):
            raise VideoServiceError(
                f"Segment count ({len(segments)}) doesn't match embedding count ({len(embeddings)})"
            )
        
        try:
            points = []
            # Use a counter to generate unique integer IDs
            # You could also use UUIDs if you prefer
            import hashlib
            
            for idx, (segment, embedding) in enumerate(zip(segments, embeddings)):
                # Create a unique integer ID by combining video_id and index
                # Use hash to create a unique integer from the string
                unique_str = f"{video_id}_{idx}"
                point_id = int(hashlib.md5(unique_str.encode()).hexdigest()[:16], 16) % (2**63 - 1)
                
                payload = {
                    'video_id': video_id,
                    'text': segment['text'],
                    'start_time': segment['start_time'],
                    'end_time': segment['end_time'],
                    'duration': segment['duration'],
                    'segment_index': idx
                }
                
                # Add optional metadata
                if metadata:
                    payload.update(metadata)
                
                points.append(
                    PointStruct(
                        id=point_id,  # Changed to integer ID
                        vector=embedding,
                        payload=payload
                    )
                )
            
            # Upsert points to Qdrant
            self.qdrant_client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )
            logger.info(f"Stored {len(points)} segments for video {video_id}")
            
        except Exception as e:
            logger.error(f"Error storing segments: {e}")
            raise VideoServiceError(f"Failed to store segments: {e}")


            
    def search_segments(self, query: str, video_id: Optional[str] = None, 
                       limit: int = 5) -> List[Dict]:
        """
        Search for relevant segments using semantic search
        
        Args:
            query: Search query
            video_id: Optional video ID to filter results
            limit: Maximum number of results to return
            
        Returns:
            List of matching segments with scores
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Build filter if video_id provided
            query_filter = None
            if video_id:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="video_id",
                            match=MatchValue(value=video_id)
                        )
                    ]
                )
            
            # Search in Qdrant
            search_results = self.qdrant_client.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=limit
            )
            
            # Format results
            results = []
            for hit in search_results:
                results.append({
                    'score': hit.score,
                    'video_id': hit.payload['video_id'],
                    'text': hit.payload['text'],
                    'start_time': hit.payload['start_time'],
                    'end_time': hit.payload['end_time'],
                    'duration': hit.payload['duration'],
                    'segment_index': hit.payload['segment_index']
                })
            
            logger.info(f"Found {len(results)} results for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching segments: {e}")
            raise VideoServiceError(f"Search failed: {e}")
    
    def process_video(self, youtube_url: str, metadata: Dict = None) -> Dict:
        """
        Main function to process a YouTube video end-to-end
        
        Steps:
        1. Extract video ID
        2. Fetch transcript
        3. Create segments
        4. Generate embeddings
        5. Store in Qdrant
        
        Args:
            youtube_url: YouTube video URL
            metadata: Optional metadata to store with segments
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Step 1: Extract video ID
            video_id = self.extract_video_id(youtube_url)
            
            # Step 2: Get transcript
            transcript = self.get_transcript(video_id)
            
            # Step 3: Create segments
            segments = self.create_segments(transcript)
            
            if not segments:
                raise VideoServiceError("No segments created from transcript. The video may not have captions or the captions are empty.")
            
            # Step 4: Generate embeddings
            segment_texts = [seg['text'] for seg in segments]
            embeddings = self.get_embeddings(segment_texts)
            
            # Step 5: Store in Qdrant
            self.store_segments(video_id, segments, embeddings, metadata)
            
            result = {
                'success': True,
                'video_id': video_id,
                'segment_count': len(segments),
                'total_duration': sum(seg['duration'] for seg in segments),
                'message': f'Successfully processed video {video_id} with {len(segments)} segments'
            }
            
            logger.info(result['message'])
            return result
            
        except VideoServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing video: {e}")
            raise VideoServiceError(f"Video processing failed: {e}")


# Convenience functions for backward compatibility
def extract_video_id(youtube_url: str) -> str:
    """Extract video ID from YouTube URL"""
    return VideoService.extract_video_id(youtube_url)


def process_video(youtube_url: str, qdrant_url: str = "localhost", 
                 qdrant_port: int = 6333, metadata: Dict = None) -> Dict:
    """Process a YouTube video"""
    service = VideoService(qdrant_url, qdrant_port)
    return service.process_video(youtube_url, metadata)


def search_segments(query: str, video_id: Optional[str] = None, limit: int = 5,
                   qdrant_url: str = "localhost", qdrant_port: int = 6333) -> List[Dict]:
    """Search for segments"""
    service = VideoService(qdrant_url, qdrant_port)
    return service.search_segments(query, video_id, limit)


