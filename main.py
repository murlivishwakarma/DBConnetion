import os
import json
from datetime import datetime
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, MetaData, Table, select, text, inspect


DEFAULT_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
CONNECT_API_KEY = os.getenv("CONNECT_API_KEY")

app = FastAPI(title="Standalone Chart API - Murli Copy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Simple DB layer (mutable engine) ---
_engine = None
metadata = MetaData()


def set_database_url(url: str):
    global _engine, metadata
    if not url:
        raise ValueError("database_url required")
    _engine = create_engine(url, future=True)
    metadata = MetaData()


def get_engine():
    global _engine
    if _engine is None:
        set_database_url(DEFAULT_DB_URL)
    return _engine


def current_database_url() -> str:
    eng = get_engine()
    return str(eng.url)


def list_tables() -> List[str]:
    eng = get_engine()
    inspector = inspect(eng)
    return inspector.get_table_names()


def get_table(table_name: str) -> Table:
    eng = get_engine()
    try:
        t = Table(table_name, metadata, autoload_with=eng)
        return t
    except Exception as exc:
        raise KeyError(f"Table '{table_name}' not found: {exc}")


def list_columns(table_name: str) -> List[str]:
    t = get_table(table_name)
    return [c.name for c in t.columns]


def run_query(table_name: str, select_columns: Optional[List[str]] = None, where: Optional[str] = None):
    eng = get_engine()
    t = get_table(table_name)
    if select_columns:
        try:
            cols = [t.c[c] for c in select_columns]
        except Exception as exc:
            raise KeyError(f"One or more selected columns not found: {exc}")
        stmt = select(*cols)
    else:
        stmt = select(t)
    if where:
        stmt = stmt.where(text(where))
    with eng.connect() as conn:
        res = conn.execute(stmt)
        rows = [dict(r._mapping) for r in res]
        return rows


# --- Pydantic models ---


class QueryRequest(BaseModel):
    table: str
    select: Optional[List[str]] = None
    where: Optional[str] = None


class PushChartRequest(BaseModel):
    name: str
    data: Any
    meta: Optional[Dict[str, Any]] = None


class ConnectRequest(BaseModel):
    database_url: str


# --- API endpoints ---


@app.get('/db-info')
def api_db_info(x_api_key: Optional[str] = Header(None)):
    # Require API key if configured
    if CONNECT_API_KEY and x_api_key != CONNECT_API_KEY:
        raise HTTPException(status_code=401, detail='Missing or invalid X-API-KEY')
    try:
        url = current_database_url()
        tables = list_tables()
        # mask password if present
        masked = url
        try:
            if '@' in url and '//' in url:
                pre, rest = url.split('//', 1)
                if ':' in rest and '@' in rest:
                    creds, after = rest.split('@', 1)
                    if ':' in creds:
                        user, pwd = creds.split(':', 1)
                        masked = f"{pre}//{user}:****@{after}"
        except Exception:
            masked = url
        return {"database_url": masked, "tables": tables}
    except Exception as exc:
        return {"database_url": current_database_url(), "tables": []}


@app.post('/connect')
def api_connect(payload: ConnectRequest, x_api_key: Optional[str] = Header(None)):
    # if CONNECT_API_KEY and x_api_key != CONNECT_API_KEY:
    #     raise HTTPException(status_code=401, detail='Missing or invalid X-API-KEY')
    try:
        set_database_url(payload.database_url)
        tables = list_tables()
        return {"connected": True, "tables": tables}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get('/tables')
def api_tables():
    try:
        return list_tables()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get('/tables/{table}/columns')
def api_columns(table: str):
    try:
        return list_columns(table)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/query')
def api_query(payload: QueryRequest):
    try:
        rows = run_query(payload.table, payload.select, payload.where)
        return rows
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


CHARTS_FILE = os.path.join(os.path.dirname(__file__), 'charts.json')


@app.post('/push-chart')
def api_push_chart(payload: PushChartRequest):
    record = {"id": datetime.utcnow().isoformat() + 'Z', "name": payload.name, "data": payload.data, "meta": payload.meta or {}}
    try:
        if os.path.exists(CHARTS_FILE):
            with open(CHARTS_FILE, 'r', encoding='utf-8') as f:
                store = json.load(f)
        else:
            store = []
        store.append(record)
        with open(CHARTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
        return {"saved": True, "record": record}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

