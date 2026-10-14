import uvicorn

if __name__ == "__main__":
    uvicorn.run('Rate_Limiter.app:app',reload=True)