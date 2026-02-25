from fastapi import FastAPI
import os
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

app = FastAPI(title=os.getenv("APP_NAME", "Circulate"))

@app.get("/healthcheck")
def read_health():
    """
    Week 1 Deliverable: Basic healthcheck endpoint.
    Returns a simple JSON status.
    """
    return {
        "status": "online", 
        "message": "Circulate API is running",
        "version": "1.0.0"
    }