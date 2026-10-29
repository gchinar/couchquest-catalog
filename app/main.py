import os
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, select, text

engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///./catalog.db'), pool_pre_ping=True)
metadata = MetaData()
games = Table('games', metadata, Column('id', String, primary_key=True),
    Column('title', String, nullable=False), Column('platform', String, nullable=False),
    Column('display_mode', String, nullable=False), Column('min_players', Integer, nullable=False),
    Column('max_players', Integer, nullable=False))

@asynccontextmanager
async def lifespan(app):
    metadata.create_all(engine)
    yield

app = FastAPI(title='CouchQuest Game Catalog', lifespan=lifespan)

class GameInput(BaseModel):
    title: str = Field(min_length=1, max_length=100, pattern=r'.*\S.*')
    platform: Literal['PC', 'Console']
    display_mode: Literal['split_screen', 'shared_screen']
    min_players: int = Field(ge=2, le=4)
    max_players: int = Field(ge=2, le=4)
    @model_validator(mode='after')
    def valid_range(self):
        if self.min_players > self.max_players:
            raise ValueError('min_players must not exceed max_players')
        return self

@app.get('/health/live')
def live(): return {'status': 'alive'}

@app.get('/health/ready')
def ready():
    try:
        with engine.connect() as c: c.execute(text('SELECT 1'))
    except Exception:
        raise HTTPException(503, 'Database unavailable')
    return {'status': 'ready'}

@app.post('/games', status_code=201)
def create_game(body: GameInput):
    game = {'id': str(uuid4()), **body.model_dump()}
    with engine.begin() as c: c.execute(games.insert().values(**game))
    return game

@app.get('/games')
def list_games(display_mode: Literal['split_screen', 'shared_screen'] | None = None,
               players: int | None = Query(None, ge=2, le=4),
               limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    q = select(games)
    if display_mode: q = q.where(games.c.display_mode == display_mode)
    if players: q = q.where(games.c.min_players <= players, games.c.max_players >= players)
    with engine.connect() as c:
        return [dict(r) for r in c.execute(q.order_by(games.c.id).limit(limit).offset(offset)).mappings()]

@app.get('/games/{game_id}')
def get_game(game_id: str):
    with engine.connect() as c:
        result = c.execute(select(games).where(games.c.id == game_id)).mappings().first()
    if not result: raise HTTPException(404, 'Game not found')
    return dict(result)
