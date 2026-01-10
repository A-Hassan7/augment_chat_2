import time

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from event_processor import EventProcessorInterface
from vector_store import VectorStoreInterface
from suggestions_service.suggestions import Suggestions
from suggestions_service.database.repositories import SuggestionsRepository

# Import user management routes
from .user_management_routes import router as user_management_router

vector_store = VectorStoreInterface()
suggestions = Suggestions()
suggestions_repo = SuggestionsRepository()


app = FastAPI(
    title="Augment Chat API",
    description="Backend API for augmented chat with user management",
    version="1.0.0",
)

origins = [
    "http://localhost",
    "http://localhost:5500",
    "http://localhost:5173",  # Vite default port
    "http://localhost:3000",  # React default port
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include user management routes
app.include_router(user_management_router)


@app.get("/transcripts")
def get_transcripts(room_id, limit=None):

    # sqlalchemy model to pydantic?
    transcripts = vector_store.get_transcripts_by_room_id(room_id=room_id, limit=limit)
    return {"messages": transcripts}


@app.post("/backfill_transcripts")
def backfill_transcripts(room_id):
    try:
        vector_store.backfill_room(room_id)
        return {"response": "backfilling in progress"}
    except:
        return {"response": "something went wrong"}


@app.get("/generate_suggestion")
def generate_suggestion(room_id, until_message_event_id=None):

    print(until_message_event_id)
    job = suggestions.generate_jokes(room_id, until_message_event_id)

    for i in range(10):

        job.refresh()
        status = job.get_status()

        if status == "finished":
            suggestions_data = suggestions_repo.get_by_room_id(
                room_id, most_recent=True
            )
            return {"suggestions": suggestions_data}

        if status == "failed":
            return {"response": f"something went wrong job id {job.id}"}

        time.sleep(2)

    return {"response": f"taking too long to complete job id: {job.id}"}


@app.get("/")
def sample():
    return {
        "messages": [
            {
                "room_id": "123",
                "message_timestamp": "2024-01-01 07:00:00",
                "transcript": "<from the server> <author> <message>",
            },
        ]
    }


if __name__ == "__main__":
    uvicorn.run("api.main:app")
