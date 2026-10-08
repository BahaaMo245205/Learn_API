import uvicorn

if __name__ == "__main__":
    uvicorn.run('Chat_Backend.app:app',reload=True)