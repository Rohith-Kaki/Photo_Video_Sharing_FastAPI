import uvicorn

#app.app:app -> reason is thie main file is inside app folder and the file name is app.py and the fast api object is created with the name app
if __name__ == "__main__":
    uvicorn.run("app.app:app", host="0.0.0.0", port=8000, reload=True)  