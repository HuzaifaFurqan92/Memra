from sqlalchemy import create_engine, Column, String, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

DATABASE_URL = "sqlite:///./memra.db"

# Note: Turned off autoflush to prevent premature object flushes before explicitly committing
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=True, bind=engine)
Base = declarative_base()

class UserModel(Base):
    __tablename__ = "users"
    
    user_id         = Column(String, primary_key=True, index=True)
    profile_json    = Column(Text, default="{}")  
    hashed_password = Column(String, nullable=False) # FIX: Changed to nullable=False for strict security

class MessageModel(Base):
    __tablename__ = "messages"
    
    id         = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id    = Column(String, index=True, nullable=False) 
    session_id = Column(String, index=True, nullable=False) # Added constraint to guarantee session safety
    role       = Column(String, nullable=False)
    content    = Column(Text, nullable=False)

def init_db():
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
    finally: 
        db.close()