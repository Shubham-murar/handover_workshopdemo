from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl
import logging
import os
from typing import Optional, List

from app.services.video_service import VideoService, VideoServiceError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title='YouTube Video Search',
    description='Search and process YouTube videos with transcript analysis using Qdrant vector database',
    version='1.0.0'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

templates = Jinja2Templates(directory="app/templates")

video_service = None


class VideoProcessRequest(BaseModel):
    url: HttpUrl
    title: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    video_id: Optional[str] = None
    limit: Optional[int] = 5


class VideoProcessResponse(BaseModel):
    success: bool
    message: str
    video_id: Optional[str] = None
    segment_count: Optional[int] = None
    total_duration: Optional[float] = None


class SearchResult(BaseModel):
    score: float
    video_id: str
    text: str
    start_time: float
    end_time: float
    duration: float
    segment_index: int


class SearchResponse(BaseModel):
    success: bool
    query: str
    results: List[SearchResult]
    count: int


@app.on_event("startup")
async def startup_event():
    global video_service
    try:
        logger.info("Starting YouTube Video Search application...")
        qdrant_url = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        logger.info(f"Connecting to Qdrant at {qdrant_url}:{qdrant_port}")
        video_service = VideoService(qdrant_url=qdrant_url, qdrant_port=qdrant_port)
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down YouTube Video Search application...")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/video/{video_id}", response_class=HTMLResponse)
async def video_page(request: Request, video_id: str):
    return templates.TemplateResponse("video.html", {"request": request, "video_id": video_id})


@app.post("/api/process", response_model=VideoProcessResponse)
async def process_video(video_request: VideoProcessRequest):
    try:
        logger.info(f"Processing video: {video_request.url}")
        metadata = {}
        if video_request.title:
            metadata['video_title'] = video_request.title
        result = video_service.process_video(youtube_url=str(video_request.url), metadata=metadata if metadata else None)
        return VideoProcessResponse(
            success=result['success'],
            message=result['message'],
            video_id=result['video_id'],
            segment_count=result['segment_count'],
            total_duration=result.get('total_duration')
        )
    except VideoServiceError as e:
        logger.error(f"Video service error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error processing video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process video: {str(e)}")


@app.post("/api/search", response_model=SearchResponse)
async def search_videos(search_request: SearchRequest):
    try:
        logger.info(f"Searching for: '{search_request.query}'")
        limit = min(max(search_request.limit, 1), 50)
        results = video_service.search_segments(query=search_request.query, video_id=search_request.video_id, limit=limit)
        search_results = [
            SearchResult(
                score=result['score'],
                video_id=result['video_id'],
                text=result['text'],
                start_time=result['start_time'],
                end_time=result['end_time'],
                duration=result['duration'],
                segment_index=result['segment_index']
            )
            for result in results
        ]
        return SearchResponse(success=True, query=search_request.query, results=search_results, count=len(search_results))
    except VideoServiceError as e:
        logger.error(f"Video service error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching videos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.delete("/api/video/{video_id}")
async def delete_video(video_id: str):
    try:
        logger.info(f"Deleting video segments for: {video_id}")
        success = video_service.delete_video_segments(video_id)
        if success:
            return {"success": True, "message": f"Deleted all segments for video {video_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete video segments")
    except VideoServiceError as e:
        logger.error(f"Video service error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {str(e)}")


@app.get("/api/health")
async def health_check():
    try:
        if video_service is None:
            return {"status": "unhealthy", "service": "YouTube Video Search", "version": "1.0.0", "error": "Video service not initialized"}
        collections = video_service.qdrant_client.get_collections()
        return {"status": "healthy", "service": "YouTube Video Search", "version": "1.0.0", "qdrant_collections": len(collections.collections)}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "service": "YouTube Video Search", "version": "1.0.0", "error": str(e)}


@app.get("/api/stats")
async def get_stats():
    try:
        collection_info = video_service.qdrant_client.get_collection(collection_name="youtube_segments")
        return {
            "success": True,
            "stats": {
                "total_segments": collection_info.points_count,
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.value,
                "collection_name": "youtube_segments"
            }
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=7860, reload=True, log_level="info")


