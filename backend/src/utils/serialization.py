import hashlib, json
from sqlalchemy import select
from src.models import User
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def _user_map(db, user_ids):
    if not user_ids: return {}
    rows = db.scalars(select(User).where(User.id.in_(set(user_ids))))
    return {u.id: {'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role} for u in rows}
def job_dict(j, user=None):
    data = {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at','computation_id','is_leader','waiting','reuse_source','joined_at','exited_at']}
    data['created_by'] = j.created_by
    data['creator'] = {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role} if user else None
    return data
def computation_dict(c, waiters=None):
    data = {k:getattr(c,k) for k in ['id','share_key','sample_fingerprint','params_fingerprint','rule_version','params','dataset_id','status','generation','stop_requested','result','error','created_by','created_at','started_at','finished_at','completed_at']}
    data['waiting_count'] = len(waiters) if waiters is not None else None
    data['waiters'] = waiters or []
    return data
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
