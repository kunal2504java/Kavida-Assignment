"""
Main entry point for the DQ Report service.
Provides REST API for querying DQ violations and runs Kafka consumer in background.
"""
import os
import sys
import logging
from typing import Optional
from pythonjsonlogger import jsonlogger

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .database import ViolationsDatabase
from .consumer import ViolationsConsumer
from .dlq_replay import DLQReplayService


def setup_logging():
    """Configure structured JSON logging."""
    logger = logging.getLogger()
    logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        timestamp=True
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logging.getLogger(__name__)


# Initialize logging
logger = setup_logging()

# Initialize FastAPI app
app = FastAPI(
    title="Data Quality Report API",
    description="REST API for querying data quality violations",
    version="1.0.0"
)

# Global instances
db: ViolationsDatabase = None
consumer: ViolationsConsumer = None
dlq_replay: DLQReplayService = None


@app.on_event("startup")
async def startup_event():
    """Initialize database and start Kafka consumer on startup."""
    global db, consumer, dlq_replay
    
    logger.info("Starting DQ Report service")
    
    # Initialize database
    db = ViolationsDatabase(db_path="/data/violations.db")
    logger.info("Database initialized")
    
    # Get Kafka configuration
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
    
    # Start Kafka consumer in background thread
    consumer = ViolationsConsumer(
        bootstrap_servers=bootstrap_servers,
        callback=db.insert_violation
    )
    consumer.start()
    logger.info("Kafka consumer started")
    
    # Initialize DLQ replay service
    dlq_replay = DLQReplayService(bootstrap_servers=bootstrap_servers)
    logger.info("DLQ replay service initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop Kafka consumer on shutdown."""
    global consumer
    
    logger.info("Shutting down DQ Report service")
    
    if consumer:
        consumer.stop()
    
    logger.info("DQ Report service stopped")


# Mount static files for dashboard
try:
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")


@app.get("/")
async def root():
    """Root endpoint - redirects to dashboard."""
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "dashboard.html"))


@app.get("/api")
async def api_root():
    """API root endpoint with service information."""
    return {
        "service": "Data Quality Report API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "/health",
            "/dq-report",
            "/dq-top-violations",
            "/dq-sample",
            "/dq-stats"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connectivity
        stats = db.get_stats()
        
        return {
            "status": "healthy",
            "database": "connected",
            "consumer": "running" if consumer and consumer.running else "stopped",
            "total_violations": stats.get("total_violations", 0)
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/dq-report")
async def get_dq_report():
    """
    Get aggregated violation counts grouped by domain, rule_name, and hour_bucket.
    
    Returns:
        List of aggregated violation records
    """
    try:
        report = db.get_aggregated_report()
        
        return {
            "total_records": len(report),
            "violations": report
        }
    except Exception as e:
        logger.error(f"Failed to generate DQ report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dq-top-violations")
async def get_top_violations(
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
    limit: int = Query(5, ge=1, le=50, description="Maximum number of results")
):
    """
    Get top N most frequent violations in the last X hours.
    
    Args:
        hours: Number of hours to look back (default: 24, max: 168)
        limit: Maximum number of results (default: 5, max: 50)
        
    Returns:
        List of top violation records
    """
    try:
        top_violations = db.get_top_violations(hours=hours, limit=limit)
        
        return {
            "hours": hours,
            "limit": limit,
            "total_records": len(top_violations),
            "top_violations": top_violations
        }
    except Exception as e:
        logger.error(f"Failed to get top violations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dq-sample")
async def get_sample_violations(
    domain: str = Query(..., description="Domain name to filter by"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records")
):
    """
    Get a sample of raw violation records for a specific domain.
    
    Args:
        domain: Domain name (e.g., 'customers', 'orders')
        limit: Maximum number of records (default: 10, max: 100)
        
    Returns:
        List of violation records
    """
    try:
        samples = db.get_sample_violations(domain=domain, limit=limit)
        
        if not samples:
            return {
                "domain": domain,
                "limit": limit,
                "total_records": 0,
                "message": f"No violations found for domain: {domain}",
                "violations": []
            }
        
        return {
            "domain": domain,
            "limit": limit,
            "total_records": len(samples),
            "violations": samples
        }
    except Exception as e:
        logger.error(f"Failed to get sample violations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dq-stats")
async def get_statistics():
    """
    Get overall database statistics.
    
    Returns:
        Statistics about violations
    """
    try:
        stats = db.get_stats()
        
        return {
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dlq/list")
async def list_dlq_topics():
    """
    List all DLQ topics and their message counts.
    
    Returns:
        List of DLQ topics with message counts
    """
    try:
        dlq_info = dlq_replay.list_dlq_topics()
        
        return {
            "dlq_topics": dlq_info,
            "total_dlq_messages": sum(t["message_count"] for t in dlq_info)
        }
    except Exception as e:
        logger.error(f"Failed to list DLQ topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/dlq/replay/{domain}")
async def replay_dlq_domain(
    domain: str,
    max_messages: Optional[int] = Query(None, description="Maximum messages to replay")
):
    """
    Replay messages from a domain's DLQ back to its raw topic.
    
    Args:
        domain: Domain name (customers, orders, lines)
        max_messages: Maximum number of messages to replay (optional)
        
    Returns:
        Replay statistics
    """
    valid_domains = ["customers", "orders", "lines"]
    
    if domain not in valid_domains:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain. Must be one of: {', '.join(valid_domains)}"
        )
    
    try:
        logger.info(f"Starting DLQ replay for domain: {domain}")
        
        stats = dlq_replay.replay_domain_dlq(
            domain=domain,
            max_messages=max_messages
        )
        
        logger.info(f"DLQ replay completed for {domain}: {stats}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to replay DLQ for {domain}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/dlq/replay-custom")
async def replay_dlq_custom(
    dlq_topic: str = Query(..., description="Source DLQ topic"),
    target_topic: str = Query(..., description="Target topic"),
    max_messages: Optional[int] = Query(None, description="Maximum messages to replay")
):
    """
    Replay messages from a custom DLQ topic to a target topic.
    
    Args:
        dlq_topic: Source DLQ topic name
        target_topic: Target topic name
        max_messages: Maximum number of messages to replay (optional)
        
    Returns:
        Replay statistics
    """
    try:
        logger.info(f"Starting custom DLQ replay from {dlq_topic} to {target_topic}")
        
        stats = dlq_replay.replay_dlq_messages(
            dlq_topic=dlq_topic,
            target_topic=target_topic,
            max_messages=max_messages
        )
        
        logger.info(f"Custom DLQ replay completed: {stats}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to replay DLQ: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Main function to run the FastAPI application."""
    logger.info("Starting DQ Report API server")
    
    # Run Uvicorn server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None  # Use our custom logging
    )


if __name__ == "__main__":
    main()
