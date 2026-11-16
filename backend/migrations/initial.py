from sqlalchemy import inspect, text
from src.config.database import Base, engine
from src import models


def _ensure_columns():
    """对已存在的表补齐新增列（create_all 只建新表，不改旧表）。

    幂等：仅添加缺失列，默认值与模型定义一致；本地演示库与 PostgreSQL 均适用。
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added_jobs_columns = False
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {col['name'] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                if table.name == 'jobs':
                    added_jobs_columns = True
                default = column.default.arg if column.default is not None and hasattr(column.default, 'arg') else None
                default_sql = ''
                if default is not None:
                    if isinstance(default, str):
                        default_sql = f" DEFAULT '{default}'"
                    elif isinstance(default, bool):
                        default_sql = f" DEFAULT {1 if default else 0}"
                    else:
                        default_sql = f" DEFAULT {default}"
                conn.execute(text(
                    f'ALTER TABLE {table.name} ADD COLUMN {column.name} '
                    f'{column.type.compile(engine.dialect)}{default_sql}'
                ))
        if added_jobs_columns:
            # 共享计算功能上线前的历史任务不挂接任何共享计算，不计入等待关系
            conn.execute(text("UPDATE jobs SET waiting=0 WHERE computation_id IS NULL"))


def migrate():
    Base.metadata.create_all(engine)
    _ensure_columns()


if __name__ == '__main__':
    migrate()
