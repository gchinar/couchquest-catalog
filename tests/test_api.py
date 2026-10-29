import importlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, 'engine', create_engine('sqlite:///'+str(tmp_path/'catalog.db')))
    with TestClient(main.app) as c: yield c

def game(**kw):
    return dict(title='Twin Trails', platform='PC', display_mode='split_screen', min_players=2, max_players=2, **kw)

def test_create_get_and_filter(client):
    r=client.post('/games',json=game()); assert r.status_code==201
    assert client.get('/games/'+r.json()['id']).json()['title']=='Twin Trails'
    assert len(client.get('/games?players=2&display_mode=split_screen').json())==1
    assert client.get('/games?players=3').json()==[]
    assert client.get('/games?display_mode=shared_screen').json()==[]

def test_invalid_range(client):
    b=game(); b.update(min_players=4,max_players=2)
    assert client.post('/games',json=b).status_code==422

def test_invalid_mode(client):
    b=game(); b['display_mode']='online_only'
    assert client.post('/games',json=b).status_code==422

def test_missing_and_health(client):
    assert client.get('/games/missing').status_code==404
    assert client.get('/health/ready').status_code==200
    assert client.get('/health/live').status_code==200
