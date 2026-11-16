import {computations,jobs} from '../api/entities.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {ComputationStatus, JobStatus, ReuseSource, Role} from '../constants/enums.js';
import {esc,date,notify} from '../utils/dom.js';
const cid=id=>'SC-'+String(id).padStart(4,'0');
export async function sharedPage(){
 const [comps,jobsList]=await Promise.all([computations.list(),jobs.list()]);
 const canWrite=session.user.role!=='viewer';
 return heading('06 / SHARED','共享计算与等待关系','相同样本内容、参数与计算规则版本的请求合用一次计算；行序不同也识别。可查待算、运行、成功、失败与停止全状态。','<button class="button" id="refresh-shared">刷新 ↻</button>')
  +(comps.length?'<div class="share-list">'+comps.map(c=>{
    const mine=jobsList.filter(j=>j.computation_id===c.id);
    return '<article class="share-card"><div class="share-card-head"><div><p class="eyebrow">'+esc(c.rule_version)+' · 第 '+esc(c.generation)+' 轮</p><h2>共享计算 '+esc(cid(c.id))+'</h2><span class="share-status '+esc(c.status)+'">'+esc(ComputationStatus[c.status]||c.status)+'</span></div>'
      +(canWrite&&['failed','stopped'].includes(c.status)?'<button class="button small primary" data-retry="'+c.id+'">恢复计算</button>':'')+'</div>'
      +'<dl class="share-meta"><div><dt>样本指纹</dt><dd title="'+esc(c.sample_fingerprint)+'">'+esc(c.sample_fingerprint.slice(0,26))+'…</dd></div>'
      +'<div><dt>参数指纹</dt><dd>'+esc(c.params_fingerprint)+'</dd></div>'
      +'<div><dt>等待请求</dt><dd>'+esc(c.waiting_count)+' 份等待 · 共 '+c.waiters.length+' 个请求</dd></div>'
      +(c.started_at?'<div><dt>开始/完成</dt><dd>'+esc(date(c.started_at))+' / '+(c.finished_at?esc(date(c.finished_at)):'—')+'</dd></div>':'')
      +(c.error?'<div><dt>失败原因</dt><dd class="share-error">'+esc(c.error)+'</dd></div>':'')+'</dl>'
      +'<ul class="share-waiter-row">'+c.waiters.map(w=>'<li><a href="#/results/'+w.job_id+'"><strong>'+esc(w.name)+'</strong>'
        +'<span>'+esc(w.creator?Role[w.creator.role]+' · '+w.creator.name:'')+' · '+esc(ReuseSource[w.reuse_source]||w.reuse_source||'')+'</span>'
        +'<span class="job-pill '+esc(w.status)+'">'+esc(JobStatus[w.status]||w.status)+'</span>'
        +'<span class="job-pill '+(w.approved?'approved':'unapproved')+'">'+(w.approved?'已批准':'待批准')+'</span></a></li>').join('')+'</ul>'
      +(mine.length?'<p class="hint">本账号相关请求 '+mine.length+' 份。各请求名称、发起人与批准状态独立保留。</p>':'')+'</article>';
  }).join('')+'</div>':'<div class="empty">尚无共享计算。到分析工作台提交一次分析后，同口径请求会自动合用。<a href="#/workbench">前往工作台 ↗</a></div>');
}
export function bindShared(refresh){
 document.querySelector('#refresh-shared')?.addEventListener('click',refresh);
 document.querySelectorAll('[data-retry]').forEach(b=>b.addEventListener('click',async()=>{
   try{await computations.retry(Number(b.dataset.retry));notify('共享计算已恢复，未重复创建计算');await refresh();}
   catch(e){notify(e.message,true);}
 }));
}
