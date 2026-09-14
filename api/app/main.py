import os
from fastapi import FastAPI

root_path = f"/pr-{os.environ['PR_NUMBER']}" if os.getenv("PR_NUMBER") else ""

app = FastAPI(
    title="SecretShare API",
    version="0.1.0",
    root_path=root_path,
)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to SecretShare API"}
