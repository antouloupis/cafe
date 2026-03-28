from fastapi import FastAPI
# from database import init_db

app = FastAPI()

# @app.on_event("startup")
# def on_startup():
#     # This ensures the .db file and tables are created inside the Docker volume
#     init_db()

@app.get("/")
def home():
    return {"status": "Cafe app is running on Python 3.14"}

