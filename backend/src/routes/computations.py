from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Computation, Job, User
from src.middlewares.auth import current_user, can_write
from src.services import computations
from src.services.audit import record
from src.utils.serialization import computation_dict
router = APIRouter(prefix='/computations')


def _waiters(db, comp_id):
    rows = db.scalars(
        select(Job).where(Job.computation_id == comp_id).order_by(Job.id)
    ).all()
    user_ids = {j.created_by for j in rows}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    return [{
        'job_id': j.id, 'name': j.name, 'status': j.status, 'waiting': j.waiting,
        'approved': j.approved, 'reuse_source': j.reuse_source, 'is_leader': j.is_leader,
        'joined_at': j.joined_at, 'exited_at': j.exited_at,
        'creator': {'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role}
        if (u := users.get(j.created_by)) else None,
    } for j in rows]


@router.get('')
def listing(db=Depends(get_db), u=Depends(current_user)):
    comps = db.scalars(select(Computation).order_by(Computation.id.desc()).limit(100)).all()
    return [computation_dict(c, _waiters(db, c.id)) for c in comps]


@router.get('/{id}')
def detail(id: int, db=Depends(get_db), u=Depends(current_user)):
    c = db.get(Computation, id)
    if not c:
        raise HTTPException(404, '共享计算不存在')
    return computation_dict(c, _waiters(db, c.id))


@router.post('/{id}/retry')
def retry(id: int, db=Depends(get_db), u=Depends(can_write)):
    c = db.get(Computation, id)
    if not c:
        raise HTTPException(404, '共享计算不存在')
    c = computations.retry(db, c, u)
    record(db, u.email, 'computation.retry', {'id': c.id, 'generation': c.generation})
    db.commit()
    computations.enqueue(c.id, c.generation)
    return computation_dict(c, _waiters(db, c.id))
