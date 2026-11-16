from fastapi import HTTPException
from src.models import Dataset
from src.services.business import metadata
from src.services import computations
def create(db, data, user):
    dataset = db.get(Dataset, data.dataset_id)
    if not dataset: raise HTTPException(404, '数据批次不存在')
    allowed={p['key']:p for p in metadata().get('parameters',[])}
    if set(data.params)-set(allowed): raise HTTPException(422,'包含未知分析参数')
    params={k:p['default'] for k,p in allowed.items()}
    params.update(data.params)
    for key,p in allowed.items():
        v=params[key]
        if p['type']=='number':
            try:
                v=float(v)
                if not (p.get('min',-1e9)<=v<=p.get('max',1e9)): raise ValueError()
                params[key]=v
            except (ValueError,TypeError): raise HTTPException(422, f'{p["label"]} 超出范围或非数值')
        elif str(v) not in [str(o['value']) for o in p.get('options',[])]:
            raise HTTPException(422,f'{p["label"]} 不是有效选项')
    name=data.name.strip()
    if len(name)<2: raise HTTPException(422,'任务名称至少需要两个字符')
    # 样本内容、参数、计算规则版本相同则合用同一份共享计算（行序无关）
    job, should_enqueue, generation = computations.join(db, dataset, params, name, user)
    db.flush()
    return job, should_enqueue, generation, job.computation_id
