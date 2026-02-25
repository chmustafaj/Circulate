from fastapi import FastAPI
import os
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

app = FastAPI(title=os.getenv("APP_NAME", "PeaceChainTRM"))

@app.get("/healthcheck")
def read_health():
    """
    Week 1 Deliverable: Basic healthcheck endpoint.
    Returns a simple JSON status.
    """
    return {
        "status": "online", 
        "message": "PeaceChainTRM API is running",
        "version": "1.0.0"
    }