import os
from fastapi import FastAPI, Depends

from app.core.auth import get_current_user

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


@app.get("/me", tags=["Auth"])
async def me(claims: dict = Depends(get_current_user)):
    """
    Returns the decoded Keycloak token claims for the current user.
    Use this to verify OAuth is wired up correctly.
    """
    return claims
