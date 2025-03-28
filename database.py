import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import urllib.parse

from dotenv import load_dotenv
load_dotenv()
# Get the database URL from environment
database_url = os.getenv("DATABASE_URL", "postgresql://owenmorris@localhost:5432/qrhunter")
print("Database URL:",database_url)

# Parse the URL to remove ssl parameters
parsed = urllib.parse.urlparse(database_url)
if parsed.scheme == "postgresql":
    # Convert to asyncpg scheme
    scheme = "postgresql+asyncpg"
else:
    scheme = parsed.scheme

# Reconstruct the URL without ssl parameters
query_params = urllib.parse.parse_qs(parsed.query)
query_params.pop('sslmode', None)  # Remove sslmode parameter
new_query = urllib.parse.urlencode(query_params, doseq=True)

# Rebuild the connection URL
database_url = urllib.parse.urlunparse((
    scheme,
    parsed.netloc,
    parsed.path,
    parsed.params,
    new_query,
    parsed.fragment
))

engine = create_async_engine(database_url, echo=True)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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