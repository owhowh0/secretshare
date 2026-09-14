from fastapi import FastAPI

app = FastAPI(
    title="SecretShare API",
    version="0.1.0",
)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to SecretShare API"}
