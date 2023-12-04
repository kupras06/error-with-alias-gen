import uvicorn

from datetime import datetime
from typing import Annotated, List, Optional
from beanie import Document, Replace, SaveChanges, Update, before_event, init_beanie
from bson import ObjectId
from pydantic.alias_generators import to_camel

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import asynccontextmanager
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from motor.motor_asyncio import AsyncIOMotorClient
from beanie.operators import Set


PyObjectId = Annotated[str, BeforeValidator(str)]


class APIModel(BaseModel):
    model_config = ConfigDict(
        # REMOVE BELOW LINE AND PUT OPERATION WORKS
        alias_generator=to_camel, 
        populate_by_name=True,
        extra="ignore",
        arbitrary_types_allowed=True,
    )


class BaseSchema(APIModel):
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()
    is_deleted: bool = Field(default=False)


class BaseDocument(Document, BaseSchema):
    # Do Not Remove. Required to map _id to id
    id: Optional[PyObjectId] = Field(description="MongoDB document ObjectID")

    @before_event([Replace, SaveChanges, Update])
    def update_created_at(self):
        self.updated_at = datetime.utcnow()


class StoresBaseIn(BaseSchema):
    name: Annotated[str, Field()]
    description: Annotated[str, Field()]


class StoresBase(StoresBaseIn):
    id: Optional[PyObjectId] = Field(description="MongoDB document ObjectID")
    pass


class StoresDB(Document, StoresBaseIn):
    pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    print("IN LIFESPAN")
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    DB = client["test"]
    await init_beanie(
        database=DB,
        document_models=[StoresDB],  # type: ignore
    )
    yield
    print("IN LIFESPAN 2")


app = FastAPI(
    root_path="/",
    openapi_url="/openapi.json",
    version="1",
    lifespan=lifespan,
)


@app.get("/", response_model=List[StoresDB])
async def get_stores():
    return await StoresDB.find().to_list()


@app.post("/", response_model=StoresBase)
async def post_stores(st_in: StoresBaseIn):
    return await StoresDB(**st_in.model_dump()).create()


@app.put("/{str_id}", response_model=StoresBase)
async def put_stores(str_id: str, st_in: StoresBaseIn):
    str1 = await StoresDB.find_one({"_id": ObjectId(str_id)})
    if str1 is None:
        raise HTTPException(404)
    await str1.update(Set(st_in.model_dump()))
    return str1


def main():
    server_data = {
        "app": "main:app",
        "host": "0.0.0.0",
        "port": 10000,
        "forwarded_allow_ips": "*",
    }
    server_data["host"] = "127.0.0.1"
    server_data["port"] = 8000
    server_data["reload"] = True
    uvicorn.run(**server_data)


if __name__ == "__main__":
    main()
