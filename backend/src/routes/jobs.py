from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.config.database import get_db
from src.models import Job, User
from src.schemas.job import JobInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import jobs, computations
from src.services.audit import record
from src.utils.serialization import job_dict
router=APIRouter(prefix='/jobs')
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    rows=list(db.scalars(select(Job).order_by(Job.id.desc()).limit(100)))
    users={x.id:x for x in db.scalars(select(User).where(User.id.in_([j.created_by for j in rows])))}
    return [job_dict(j,users.get(j.created_by)) for j in rows]
@router.post('',status_code=201)
def create(data:JobInput,db=Depends(get_db),u=Depends(can_write)):
    try:
        j, should_enqueue, generation, comp_id = jobs.create(db,data,u)
    except IntegrityError:
        # 并发下唯一 share_key 冲突：回滚后重新合用已存在的共享计算
        db.rollback()
        j, should_enqueue, generation, comp_id = jobs.create(db,data,u)
    record(db,u.email,'job.create',{'id':j.id,'computation_id':comp_id,'reuse_source':j.reuse_source,'params':j.params})
    db.commit()
    # 仅首份/重新激活的计算投递；合用请求不重复投递
    if should_enqueue:
        computations.enqueue(comp_id, generation)
    return job_dict(j, u)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    return job_dict(j, db.get(User, j.created_by))
@router.post('/{id}/exit')
def exit_wait(id:int,db=Depends(get_db),u=Depends(can_write)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    j, comp, stopped = computations.exit_wait(db,j,u)
    record(db,u.email,'job.exit',{'id':id,'computation_id':comp.id,'stopped':stopped})
    db.commit()
    return job_dict(j, db.get(User, j.created_by))
@router.post('/{id}/approve')
def approve(id:int,db=Depends(get_db),u=Depends(admin_only)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    if j.status!='completed':raise HTTPException(409,'仅已完成结果可以批准')
    j.approved=True; record(db,u.email,'job.approve',{'id':id}); db.commit()
    return job_dict(j, db.get(User, j.created_by))
