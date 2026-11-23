import { download, get, importFile, post } from '../api/client.js';
import { table } from '../components/common/data.js';
import { intro } from '../components/common/frame.js';
import { fieldControl, formError } from '../components/common/forms.js';
import { Role } from '../constants/enums.js';
import { bindDownloads, bindForm, notify } from '../hooks/actions.js';
import { formValues } from '../types/form.js';
import { esc, timeLabel } from '../utils/html.js';

export async function observationPage(spec, user, route) {
  const offset = Math.max(0, Number.parseInt(route.id, 10) || 0);
  const [{total, items}, assignments] = await Promise.all([
    get(`/observations?offset=${offset}&limit=20`), get('/assignments'),
  ]);
  const writable = user.role !== Role.VIEWER;
  const tools = writable ? `<div class="tools"><details><summary>登记或订正一条分派</summary><form id="assignment-form"><div class="form-grid">${spec.assignment_fields.map(field => fieldControl(field)).join('')}</div>${formError}<button class="primary">保存分派</button></form></details>
    <details><summary>按模板导入分派表 CSV</summary><form id="assignment-import-form"><p>使用 UTF-8 CSV，每次最多 500 条。与当前分派一致的记录自动跳过，同一班组的新记录视为订正。</p><button type="button" data-download="/assignments/template">下载模板</button><label class="field"><span>CSV 文件</span><input type="file" name="file" accept=".csv,text/csv" required></label>${formError}<button class="primary">导入分派表</button></form></details>
    <details><summary>登记一条${esc(spec.record_name)}</summary><form id="record-form"><div class="form-grid">${spec.fields.map(field => fieldControl(field)).join('')}</div>${formError}<button class="primary">保存记录</button></form></details>
    <details><summary>按模板导入工票 CSV</summary><form id="import-form"><p>使用 UTF-8 CSV，每次最多 500 条。重复行自动跳过。</p><button type="button" data-download="/observations/template">下载模板</button><label class="field"><span>CSV 文件</span><input type="file" name="file" accept=".csv,text/csv" required></label>${formError}<button class="primary">导入文件</button></form></details></div>` : '';
  return `${intro('数据台账', spec.source, `<span class="count">${total} <small>条${esc(spec.record_name)}</small></span>`)}
    ${tools}
    <section class="panel"><div class="panel-heading"><h2>${esc(spec.assignment_name)}</h2><small>分派表与工票可按任意先后到达，分析以提交时固化的两份依据对账</small></div>
    ${table([{key:'team',label:'压印班组'},{key:'machine',label:'机型'},{key:'arm',label:'分派参数'},{key:'note',label:'订正说明'},{label:'生效时间',html:row => timeLabel(row.created_at)}], assignments.map(item => ({...item.data, created_at:item.created_at})), '暂无分派记录。发起分析前请先登记或导入分派表。')}</section>
    <section class="panel"><div class="panel-heading"><h2>${esc(spec.record_name)}明细</h2>${writable ? '<a class="text-link" href="#analysis">发起分析 →</a>' : ''}</div>
    ${table([{key:'id',label:'记录号'},...spec.fields], items.map(item => ({id:item.id,...item.data})), '暂无观测。分析员可先导入 CSV 或登记样本。')}
    ${total ? `<div class="pagination"><span>第 ${offset + 1}–${Math.min(total,offset + 20)} 条</span>${offset > 0 ? `<a href="#observations/${Math.max(0, offset-20)}">上一页</a>` : ''}${offset+20 < total ? `<a href="#observations/${offset+20}">下一页</a>` : ''}</div>` : ''}</section>`;
}

export function wireObservations(root, spec, refresh) {
  bindDownloads(root, download);
  bindForm(root.querySelector('#record-form'), async form => {
    await post('/observations', formValues(form, spec.fields));
    notify('记录已保存');
    if (location.hash === '#observations' || !location.hash) refresh();
    else location.hash = '#observations';
  });
  bindForm(root.querySelector('#import-form'), async form => {
    const report = await importFile(form.elements.file.files[0]);
    notify(`已导入 ${report.added} 条 · 跳过 ${report.skipped} 条重复记录`);
    refresh();
  });
  bindForm(root.querySelector('#assignment-form'), async form => {
    await post('/assignments', formValues(form, spec.assignment_fields));
    notify('分派记录已保存');
    refresh();
  });
  bindForm(root.querySelector('#assignment-import-form'), async form => {
    const report = await importFile(form.elements.file.files[0], '/assignments/import');
    notify(`已导入 ${report.added} 条分派 · 跳过 ${report.skipped} 条`);
    refresh();
  });
}
