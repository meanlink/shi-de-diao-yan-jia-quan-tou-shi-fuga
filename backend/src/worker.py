import time, json, logging
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import Job, Computation, Dataset, Report
from src.services.business import analyze
from src.services.reports import deliver
from src.services.audit import record
from src.services import computations
logging.basicConfig(level=logging.INFO)


def _set_waiter_status(db, comp_id, status, **fields):
    waiters = db.scalars(
        select(Job).where(Job.computation_id == comp_id, Job.waiting == True)  # noqa: E712
    )
    for j in waiters:
        j.status = status
        for key, value in fields.items():
            setattr(j, key, value)


def finalize_inflight(db, comp, generation, result=None, error=None):
    """运行中计算的完成检查点（同一会话内调用）。

    - 停止请求 / 轮次被取代：成功结果丢弃、转 stopped（失败项留待恢复）；
    - 正常成功：结果与所有等待请求一起生效；
    - 计算失败：标记 failed，等待请求留待恢复。
    返回最终状态字符串。
    """
    now = time.time()
    if error is None:
        if comp.stop_requested or comp.generation != generation or comp.status != 'running':
            logging.info('Discard result of stopped/superseded computation id=%s', comp.id)
            if comp.status == 'running':
                comp.status = 'stopped'
                comp.finished_at = now
                _set_waiter_status(db, comp.id, 'exited', finished_at=now, waiting=False)
            record(db, 'worker', 'computation.stopped', {'id': comp.id})
            return comp.status
        comp.result = result
        comp.status = 'completed'
        comp.finished_at = now
        comp.completed_at = now
        # 结果与等待请求一起生效：各自保留名称、发起人与批准状态
        for j in db.scalars(select(Job).where(Job.computation_id == comp.id)):
            if j.waiting and j.status in ('queued', 'running'):
                j.result = result
                j.status = 'completed'
                j.finished_at = now
                j.waiting = False
        record(db, 'worker', 'computation.completed',
               {'id': comp.id, 'waiters': computations.waiting_count(db, comp.id)})
        return 'completed'
    # 失败路径：被新一轮取代的迟到失败返回直接丢弃
    if comp.generation != generation:
        logging.info('Drop failure from superseded generation id=%s', comp.id)
        return comp.status
    comp.status = 'failed'
    comp.error = str(error)[:990]
    comp.finished_at = now
    # 失败项留待恢复：等待请求标记失败，但仍挂在同一共享计算上（waiting 保持 True）
    _set_waiter_status(db, comp.id, 'failed', error=comp.error, finished_at=now)
    record(db, 'worker', 'computation.failed', {'id': comp.id, 'error': comp.error})
    return 'failed'


def execute(comp_id, generation):
    """执行一份共享计算。generation 不匹配的迟到消息直接忽略。"""
    with Session() as db:
        comp = db.get(Computation, comp_id)
        if not comp:
            return
        # 旧一轮计算晚返回：不启动、不污染新尝试
        if comp.generation != generation or comp.status != 'pending':
            logging.info('Skip stale computation message id=%s gen=%s current=%s status=%s',
                         comp_id, generation, comp.generation, comp.status)
            return
        dataset = db.get(Dataset, comp.dataset_id)
        if not dataset:
            comp.status = 'failed'
            comp.error = '关联数据批次不存在'
            comp.finished_at = time.time()
            for j in db.scalars(select(Job).where(Job.computation_id == comp.id, Job.waiting == True)):  # noqa: E712
                j.status='failed'; j.error=comp.error; j.finished_at=comp.finished_at; j.waiting=False
            record(db, 'worker', 'computation.failed', {'id': comp.id, 'error': comp.error})
            db.commit()
            return
        comp.status = 'running'
        comp.started_at = time.time()
        _set_waiter_status(db, comp.id, 'running')
        record(db, 'worker', 'computation.running', {'id': comp.id, 'generation': generation})
        db.commit()
        try:
            result = analyze(dataset.records, comp.params)
            json.dumps(result, allow_nan=False)
            db.refresh(comp)
            finalize_inflight(db, comp, generation, result=result)
        except Exception as e:
            logging.exception('Shared computation failed')
            db.refresh(comp)
            finalize_inflight(db, comp, generation, error=e)
        db.commit()


def tick():
    # 持久兜底：Redis 消息丢失时直接拾取待算共享计算
    with Session() as db:
        pending = computations.claim_pending(db)
    for comp_id in pending:
        with Session() as db:
            comp = db.get(Computation, comp_id)
            gen = comp.generation if comp else None
        if gen is not None:
            execute(comp_id, gen)
    with Session() as db:
        for r in db.scalars(select(Report).where(Report.enabled == True, Report.next_run <= time.time())):
            d = deliver(db, r)
            if d: record(db, 'worker', 'report.delivered', {'id': r.id, 'delivery': d.id})
        db.commit()


def main():
    r = Redis.from_url(REDIS_URL, socket_timeout=3)
    # 单 worker 崩溃恢复：运行中的共享计算回到待算并抬升 generation，
    # 使崩溃前在途的旧消息失效；重试不重复创建计算。
    with Session() as db:
        recovered = computations.recover_running(db)
        for comp_id in recovered:
            record(db, 'worker', 'computation.recovered', {'id': comp_id})
        db.commit()
    while True:
        Path('/tmp/heartbeat').touch()
        try:
            item = r.blpop('analysis:queue', timeout=1)
            if item:
                token = item[1].decode()
                if ':' in token:
                    comp_id, generation = token.split(':', 1)
                    execute(int(comp_id), int(generation))
                else:
                    # 兼容旧格式消息
                    execute(int(token), 0)
            tick()
        except Exception:
            logging.exception('Worker retry'); time.sleep(2)
if __name__ == '__main__': main()
