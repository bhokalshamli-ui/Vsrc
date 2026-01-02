# Add these test endpoints to main.py for debugging

@app.get("/test/{media_type}/{id}")
async def test_vidsrc(
    media_type: str,
    id: str,
    season: int = None,
    episode: int = None
):
    """Test endpoint - shows full extraction process"""
    provider = providers.get("vidsrc")
    result = await provider.get_streams(media_type, id, season, episode)
    
    # Add debugging info
    debug_info = {
        "endpoint": f"/vidsrc/{media_type}/{id}",
        "direct_sources": result["sources"][:3] if result["sources"] else [],
        "source_count": len(result["sources"]),
        "has_error": bool(result["error"])
    }
    
    return {
        **result,
        "debug": debug_info
    }

@app.get("/health")
async def health_check():
    return {"status": "working", "providers": list(providers.keys())}
