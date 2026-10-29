import uvicorn

if __name__ == "__main__":
    #           "Name_Folder.app:app"
    uvicorn.run('Notifications.app:app',reload=True)