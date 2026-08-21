from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import settings

# async engine database connection pool
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,  # not settings.PRODUCTION,
)

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session
