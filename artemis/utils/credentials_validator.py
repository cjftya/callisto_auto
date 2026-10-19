"""Callisto uses official local CLI login, never API-key validation endpoints."""
async def validate_api_key(*args, **kwargs):
    raise ValueError("API-key validation is disabled; use the provider CLI official login")
