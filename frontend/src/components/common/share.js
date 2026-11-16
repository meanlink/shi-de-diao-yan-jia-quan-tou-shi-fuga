import {ComputationStatus, JobStatus, ReuseSource, Role} from '../../constants/enums.js';
import {esc, date} from '../../utils/dom.js';

const badge = status => '<span class="share-status ' + esc(status) + '">' + esc(ComputationStatus[status] || status) + '</span>';

export function sharePanel(job, comp, currentUser) {
 if (!job || !job.computation_id) return '';
 const cid = 'SC-' + String(job.computation_id).padStart(4, '0');
 const source = ReuseSource[job.reuse_source] || job.reuse_source || '';
 const relation = !job.waiting && job.status === 'completed' ? '已领取共享结果'
   : job.status === 'exited' ? '已退出等待'
   : job.is_leader ? '首份发起 · 等待中' : '合用等待中';
 let body = '<div class="share-head"><div><span class="eyebrow">SHARED COMPUTATION</span>'
   + '<h3>共享计算 ' + esc(cid) + '</h3></div>'
   + (comp ? badge(comp.status) : '') + '</div>';
 body += '<dl class="share-meta">'
   + '<div><dt>共享编号</dt><dd>#' + esc(cid) + '</dd></div>'
   + (source ? '<div><dt>复用来源</dt><dd>' + esc(source) + '</dd></div>' : '')
   + '<div><dt>本请求关系</dt><dd>' + esc(relation) + '</dd></div>'
   + (comp ? '<div><dt>计算规则</dt><dd>' + esc(comp.rule_version) + ' · 第 ' + esc(comp.generation) + ' 轮</dd></div>' : '')
   + '<div><dt>发起人</dt><dd>' + esc(job.creator ? job.creator.name : ('#' + job.created_by)) + '</dd></div>'
   + '</dl>';
 if (comp) {
   if (comp.error) body += '<p class="warning">共享计算失败：' + esc(comp.error) + '</p>';
   body += '<div class="share-waiters"><div class="section-title"><h2>等待关系</h2><span>'
     + esc(comp.waiting_count) + ' 份等待中 · 共 ' + comp.waiters.length + ' 个请求</span></div><ul>';
   for (const w of comp.waiters) {
     body += '<li class="' + (w.waiting ? 'is-waiting' : 'is-done') + '">'
       + '<div><strong>' + esc(w.name) + '</strong>'
       + (w.is_leader ? '<em>首份</em>' : '')
       + '<span>' + esc(w.creator ? Role[w.creator.role] + ' · ' + w.creator.name : '发起人 #' + (w.creator?.id || '')) + '</span>'
       + (w.joined_at ? '<small>加入 ' + esc(date(w.joined_at)) + '</small>' : '')
       + '</div><div class="share-tags"><span class="job-pill ' + esc(w.status) + '">' + esc(JobStatus[w.status] || w.status) + '</span>'
       + '<span class="job-pill ' + (w.approved ? 'approved' : 'unapproved') + '">' + (w.approved ? '已批准' : '待批准') + '</span></div></li>';
   }
   body += '</ul></div>';
   const canWrite = currentUser && currentUser.role !== 'viewer';
   const canExit = canWrite && job.waiting && ['queued', 'running', 'failed'].includes(job.status);
   const canRetry = canWrite && ['failed', 'stopped'].includes(comp.status);
   if (canExit || canRetry) {
     body += '<div class="share-actions">';
     if (canExit) body += '<button class="button small" id="exit-wait">退出等待</button>';
     if (canRetry) body += '<button class="button small primary" id="retry-comp">恢复共享计算</button>';
     body += '<p class="hint">最后一份请求退出才会停止计算；恢复不重复创建计算。</p></div>';
   }
 }
 return '<section class="panel share-panel">' + body + '</section>';
}
