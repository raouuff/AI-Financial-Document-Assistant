"""Run the app:  python run.py  (or: uvicorn app.main:app --reload)"""
import uvicorn

from app.config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
