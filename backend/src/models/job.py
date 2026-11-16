from sqlalchemy import String, JSON, Double, ForeignKey, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(String(1000), default='')
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    finished_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    # 共享计算关联：多个 Job 可合用同一 Computation；leader 是首个发起的请求。
    computation_id: Mapped[int | None] = mapped_column(ForeignKey('computations.id'), nullable=True)
    is_leader: Mapped[bool] = mapped_column(Boolean, default=False)
    waiting: Mapped[bool] = mapped_column(Boolean, default=True)
    reuse_source: Mapped[str] = mapped_column(String(40), default='')
    joined_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    exited_at: Mapped[float | None] = mapped_column(Double, nullable=True)
