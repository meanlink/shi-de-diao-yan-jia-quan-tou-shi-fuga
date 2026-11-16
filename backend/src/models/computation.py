from sqlalchemy import String, JSON, Double, Integer, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class Computation(Base):
    """共享计算：相同样本内容、参数与计算规则版本的请求合用同一份计算。

    一个 Computation 承载多个等待请求（Job）。状态机：
    pending（待算）→ running（运行中）→ completed（成功）/ failed（失败）；
    pending/running 可在最后一份等待退出后转入 stopped（已停止）。
    generation 在每次（重新）投递计算时递增，用于识别旧计算的迟到返回，
    旧 generation 完成的结果不得污染新一轮尝试。
    """
    __tablename__ = 'computations'
    __table_args__ = (
        UniqueConstraint('share_key', name='uq_computations_share_key'),
        Index('ix_computations_status', 'status'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    share_key: Mapped[str] = mapped_column(String(220))
    sample_fingerprint: Mapped[str] = mapped_column(String(90))
    params_fingerprint: Mapped[str] = mapped_column(String(40))
    rule_version: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    dataset_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    generation: Mapped[int] = mapped_column(Integer, default=1)
    stop_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(String(1000), default='')
    created_by: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[float] = mapped_column(Double)
    started_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    finished_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    completed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
