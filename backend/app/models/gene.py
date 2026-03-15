from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Gene(Base):
    __tablename__ = "genes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'int', 'float', 'enum'
    low = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    decimals = Column(Integer, nullable=True)
    options = Column(Text, nullable=True)  # comma-separated values for enum type
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False, default=0)

    project = relationship("Project", back_populates="genes")
