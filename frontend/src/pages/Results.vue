<script setup lang="ts">
import {ref,computed,onMounted,onUnmounted,watch} from 'vue';
import {route} from '../router';
import {runs} from '../stores/runs';
import {reviews} from '../stores/reviews';
import {canWrite} from '../stores/auth';
import {useTask} from '../hooks/useTask';
import {fixed} from '../utils/format';
import {fetchRunSample,fetchRunPoints} from '../api/runs';
import type {Point} from '../types/domain';
import PageHeading from '../components/common/PageHeading.vue';
import StatusPill from '../components/common/StatusPill.vue';
import Notice from '../components/common/Notice.vue';
import EmptyState from '../components/common/EmptyState.vue';
import CalibrationMetrics from '../components/CalibrationMetrics.vue';
import AgreementPlot from '../components/AgreementPlot.vue';
import PairTable from '../components/PairTable.vue';

const selected=ref(route.value.query.get('run')||'demo-run'),
 action=ref('对照量程与重复测量依据复核比例偏倚，检查界限外配对；BA界限不是CI，不据此直接宣称探头可互换。'),
 notice=ref('');
watch(()=>route.value.query.get('run'),v=>{selected.value=v||'demo-run'});
const {error,busy,act}=useTask();
let timer:ReturnType<typeof setInterval>;

const run=computed(()=>runs.items.value.find(r=>r.id===selected.value));
const result=computed(()=>run.value?.result);
const sample=ref<Point[]>([]),sampleNote=ref(''),sampleError=ref('');
const points=ref<Point[]>([]),after=ref<number|null>(0),pointTotal=ref(0),pointsLoading=ref(false),pointsError=ref('');

async function loadSample(){
 if(!run.value||run.value.status!=='completed')return;
 try{
  const payload=await fetchRunSample(run.value.id);
  sample.value=payload.items;sampleNote.value=payload.note;
 }catch(e){sampleError.value=(e as Error).message}
}
async function loadPoints(reset:boolean){
 if(!run.value)return;
 pointsLoading.value=true;pointsError.value='';
 try{
  const page=await fetchRunPoints(run.value.id,reset?0:(after.value||0),100);
  points.value=reset?page.items:points.value.concat(page.items);
  after.value=page.next_after;pointTotal.value=page.total;
 }catch(e){pointsError.value=(e as Error).message}finally{pointsLoading.value=false}
}
async function refresh(){
 await runs.load();
 if(run.value?.status==='completed'&&sample.value.length===0){await loadSample();await loadPoints(true)}
}
onMounted(async()=>{await refresh();timer=setInterval(runs.load,2000)});
onUnmounted(()=>clearInterval(timer));
watch(selected,()=>{sample.value=[];points.value=[];after.value=0;refresh()});

function submit(){act(async()=>{await reviews.create({run_id:selected.value,action:action.value});notice.value='偏倚复核已提交，等待管理员批准。'})}
</script>
<template>
<PageHeading index="04 / 运行底稿" title="校准关系，与差值分布一并复核。" note="两图都来自同一批持久化Python结果。图表只画有界抽样并标注抽样量；统计、越界计数与底稿明细分页使用全部读数。Deming不是单侧OLS，BA界限不是偏倚置信区间。"/>
<div class="result-toolbar">
 <label>运行记录<select v-model="selected"><option v-for="r in runs.items.value" :key="r.id" :value="r.id">{{r.id==='demo-run'?'三量程基线':r.id.slice(0,8)}} · {{r.status}}</option></select></label>
 <StatusPill v-if="run" :status="run.status"/>
</div>
<Notice :message="error||runs.error.value"/>
<Notice v-if="run?.status==='failed'" :message="run.error"/>
<EmptyState v-if="run&&['queued','running'].includes(run.status)" :text="`独立worker正在流式计算Deming、BA与比例偏倚（当前阶段 ${run.phase}，已处理 ${run.progress} 组），结果每两秒刷新。`"/>
<template v-if="run?.status==='completed'&&result">
 <CalibrationMetrics :result="result"/>
 <Notice :message="sampleError"/>
 <div class="result-plots">
  <section><h2>Deming校准散点</h2><AgreementPlot :points="sample" :result="result" mode="deming"/></section>
  <section><h2>Bland–Altman差值图</h2><AgreementPlot :points="sample" :result="result" mode="ba"/></section>
 </div>
 <p class="sample-note">图中显示 {{result.sample_size}} / {{result.n}} 组（{{result.sample_note}}）</p>
 <div class="result-columns">
  <section>
   <h2>界限外配对与全部底稿</h2>
   <Notice :message="pointsError"/>
   <PairTable :rows="points"/>
   <div class="pager">
    <small>已载入 {{points.length}} / {{pointTotal}} 组</small>
    <button v-if="after!==null" class="secondary" :disabled="pointsLoading" @click="loadPoints(false)">继续加载 100 组 ↓</button>
   </div>
   <form v-if="canWrite()" class="review-form" @submit.prevent="submit">
    <label>偏倚复核说明<textarea v-model="action" rows="4" required minlength="8"></textarea></label>
    <button :disabled="busy">提交偏倚复核</button><p class="success" v-if="notice">{{notice}}</p>
   </form>
  </section>
  <aside class="field-note">
   <p class="eyebrow">METHOD & LIMITS</p>
   <h3>比例偏倚回归</h3>
   <p v-if="result.agreement.proportional.estimable">差值={{fixed(result.agreement.proportional.intercept)}} + {{fixed(result.agreement.proportional.slope,4)}} × 均值</p>
   <p v-else>{{result.agreement.proportional.reason}}</p>
   <p>有效 {{result.n}} 组，界限外 {{result.agreement.outside_loa}} 组；讨论容差 ±{{result.tolerance}} {{result.unit}} 外 {{result.outside_tolerance}} 组。</p>
   <p>y方向残差RMSE {{fixed(result.deming.residual_rmse_y)}} {{result.unit}}，仅作拟合残差摘要。</p>
   <p class="note-rule">{{result.agreement.limits_note}} 若差值随均值变化或方差不齐，应先讨论量程/变换口径。</p>
  </aside>
 </div>
</template>
</template>
