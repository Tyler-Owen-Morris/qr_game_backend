from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Create the base class for declarative models
class Base(DeclarativeBase):
    pass

# Convert standard postgres:// URLs to postgresql:// for asyncpg
from config import settings
database_url = settings.DATABASE_URL.replace('postgres://', 'postgresql+asyncpg://')

# Create async engine
engine = create_async_engine(
    database_url,
    echo=True,
    future=True
)

# Configure async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Dependency to get DB sessions
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()