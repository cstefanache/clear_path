from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    genes_description = Column(Text, nullable=True)
    objectives_description = Column(Text, nullable=True)
    constraints_description = Column(Text, nullable=True)
    fitness_function_code = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="projects")
    chat_messages = relationship("ChatMessage", back_populates="project", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    executions = relationship("Execution", back_populates="project", cascade="all, delete-orphan", order_by="Execution.created_at.desc()")
    genes = relationship("Gene", back_populates="project", cascade="all, delete-orphan", order_by="Gene.order")
