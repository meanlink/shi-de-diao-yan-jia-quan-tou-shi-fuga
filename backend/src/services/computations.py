"""共享计算编排：合用、领取、恢复、退出与状态流转。"""
import time

from fastapi import HTTPException
from redis import Redis
from sqlalchemy import select, func

from src.config.settings import REDIS_URL
from src.constants import rules
from src.models import Computation, Job
from src.utils.fingerprint import sample_fingerprint, params_fingerprint

# 终态之外、仍在等待结果的任务状态；failed 仍挂接等待恢复，也可主动退出
WAIT_STATUSES = ('queued', 'running', 'failed')
ACTIVE_COMP_STATUSES = ('pending', 'running')


def enqueue(comp_id, generation):
    """投递共享计算消息，附带 generation 以识别旧一轮的迟到消息。"""
    try:
        r = Redis.from_url(REDIS_URL)
        r.rpush('analysis:queue', f'{comp_id}:{generation}')
        r.close()
    except Exception:
        pass  # SQL 中 pending 状态是持久兜底，worker 兜底轮询会拾取


def _fingerprints(dataset, params):
    sfp = sample_fingerprint(dataset.records)
    pfp = params_fingerprint(params)
    return sfp, pfp, f'{sfp}|{pfp}|{rules.CALC_RULE_VERSION}'


def join(db, dataset, params, name, user):
    """按 样本内容+参数+规则版本 查找或创建共享计算，并挂接一个新请求。

    返回 (job, should_enqueue, generation)。调用方在提交后负责投递队列。
    行锁保证并发请求只会得到同一份共享计算，不会重复创建。
    """
    sfp, pfp, key = _fingerprints(dataset, params)
    now = time.time()
    comp = db.scalar(
        select(Computation).where(Computation.share_key == key).with_for_update()
    )
    if comp is None:
        # 首份请求：创建唯一的共享计算
        comp = Computation(
            share_key=key, sample_fingerprint=sfp, params_fingerprint=pfp,
            rule_version=rules.CALC_RULE_VERSION, params=params, dataset_id=dataset.id,
            status='pending', generation=1, stop_requested=False,
            created_by=user.id, created_at=now,
        )
        db.add(comp)
        db.flush()
        job = _new_job(db, name, dataset, params, user, comp, now,
                       is_leader=True, reuse_source='leader', waiting=True, status='queued')
        return job, True, comp.generation

    if comp.status in ACTIVE_COMP_STATUSES:
        # 合用正在进行的计算；新请求若赶上停止请求，撤回停止标记（又有等待者了）
        comp.stop_requested = False
        job = _new_job(db, name, dataset, params, user, comp, now,
                       is_leader=False, reuse_source='shared', waiting=True,
                       status='running' if comp.status == 'running' else 'queued')
        return job, False, comp.generation

    if comp.status == 'completed':
        # 后来的请求直接领取已有成功结果，不再启动计算
        job = _new_job(db, name, dataset, params, user, comp, now,
                       is_leader=False, reuse_source='shared', waiting=False,
                       status='completed')
        job.result = comp.result
        job.finished_at = now
        return job, False, comp.generation

    # failed / stopped：留待恢复的失败项被新请求重新激活，沿用同一行（不重复创建计算）
    comp.status = 'pending'
    comp.generation += 1
    comp.stop_requested = False
    comp.error = ''
    comp.result = {}
    comp.started_at = None
    comp.finished_at = None
    # 此前失败、仍在等待恢复的请求重新进入等待；已退出的请求保持退出
    for old in db.scalars(select(Job).where(Job.computation_id == comp.id, Job.waiting == True)):  # noqa: E712
        old.status = 'queued'
        old.error = ''
    db.flush()
    job = _new_job(db, name, dataset, params, user, comp, now,
                   is_leader=False, reuse_source='retry', waiting=True, status='queued')
    return job, True, comp.generation


def _new_job(db, name, dataset, params, user, comp, now, *, is_leader, reuse_source, waiting, status):
    job = Job(
        name=name, dataset_id=dataset.id, params=params, created_by=user.id,
        created_at=now, status=status, computation_id=comp.id, is_leader=is_leader,
        waiting=waiting, reuse_source=reuse_source, joined_at=now,
    )
    db.add(job)
    db.flush()
    return job


def waiting_count(db, comp_id):
    return db.scalar(
        select(func.count()).select_from(Job)
        .where(Job.computation_id == comp_id, Job.waiting == True)  # noqa: E712
    )


def exit_wait(db, job, user):
    """请求退出等待；最后一份退出才停止共享计算。"""
    if user.role != 'admin' and job.created_by != user.id:
        raise HTTPException(403, '只能退出自己发起的等待请求')
    if not job.waiting or job.status not in WAIT_STATUSES:
        raise HTTPException(409, '该请求不在等待中，无法退出')
    comp = db.get(Computation, job.computation_id)
    if not comp:
        raise HTTPException(409, '请求未挂接共享计算')
    now = time.time()
    job.waiting = False
    job.status = 'exited'
    job.exited_at = now
    others = waiting_count(db, comp.id)
    stopped = False
    if others == 0:
        if comp.status == 'pending':
            # 待算立即停止；抬升 generation 使队列中旧一轮消息在入口守卫处失效
            comp.stop_requested = True
            comp.generation += 1
            comp.status = 'stopped'
            comp.finished_at = now
            stopped = True
        elif comp.status == 'running':
            # 运行中不打断计算，仅请求停止；由 worker 在完成检查点丢弃迟到结果
            comp.stop_requested = True
        elif comp.status == 'failed':
            # 失败项全部退出后，失败计算不再被任何请求等待，标记已停止
            comp.status = 'stopped'
            comp.finished_at = now
            stopped = True
    return job, comp, stopped


def retry(db, comp, user):
    """恢复失败/已停止的共享计算：不新建计算，仅抬升 generation 重新投递。"""
    if comp.status not in ('failed', 'stopped'):
        raise HTTPException(409, '仅失败或已停止的共享计算可以恢复')
    comp.status = 'pending'
    comp.generation += 1
    comp.stop_requested = False
    comp.error = ''
    comp.result = {}
    comp.started_at = None
    comp.finished_at = None
    now = time.time()
    for old in db.scalars(select(Job).where(Job.computation_id == comp.id, Job.waiting == True)):  # noqa: E712
        old.status = 'queued'
        old.error = ''
    db.flush()
    return comp


def claim_pending(db, limit=3):
    """worker 兜底轮询：拾取待算共享计算（Redis 消息丢失时的持久路径）。"""
    return list(db.scalars(
        select(Computation.id).where(Computation.status == 'pending').limit(limit)
    ))


def recover_running(db):
    """worker 启动恢复：崩溃前运行中的共享计算回到待算并抬升 generation。

    抬升 generation 使崩溃前在途的旧消息失效；恢复不创建新计算。
    """
    recovered = []
    for comp in db.scalars(select(Computation).where(Computation.status == 'running')):
        comp.status = 'pending'
        comp.generation += 1
        comp.stop_requested = False
        recovered.append(comp.id)
        for j in db.scalars(
            select(Job).where(Job.computation_id == comp.id, Job.waiting == True)  # noqa: E712
        ):
            j.status = 'queued'
    return recovered
