<script setup lang="ts">
import {ref,onMounted} from 'vue';
import {reviews} from '../stores/reviews';
import {reports} from '../stores/reports';
import {isAdmin} from '../stores/auth';
import {request} from '../api/client';
import {downloadCsv} from '../api/client';
import {fetchReportPoints} from '../api/reports';
import {useTask} from '../hooks/useTask';
import type {Point} from '../types/domain';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import StatusPill from '../components/common/StatusPill.vue';
import CalibrationMetrics from '../components/CalibrationMetrics.vue';
import PairTable from '../components/PairTable.vue';
const expanded=ref(''),detailId=ref(''),detailRows=ref<Point[]>([]),after=ref<number|null>(0),total=ref(0),detailLoading=ref(false),detailError=ref('');
const {error,busy,act}=useTask();
onMounted(()=>Promise.all([reviews.load(),reports.load()]));
function approve(id:string){act(async()=>{await request('/reviews/'+id+'/approve','POST');await reviews.load()})}
function publish(id:string){act(async()=>{await reports.create({review_id:id,title:'双探头校准底稿 '+new Date().toLocaleDateString()});await reports.load()})}
function download(id:string){act(()=>downloadCsv(id))}
async function loadDetail(reset:boolean){
 if(!detailId.value)return;
 detailLoading.value=true;detailError.value='';
 try{
  const page=await fetchReportPoints(detailId.value,reset?0:(after.value||0),100);
  detailRows.value=reset?page.items:detailRows.value.concat(page.items);
  after.value=page.next_after;total.value=page.total;
 }catch(e){detailError.value=(e as Error).message}finally{detailLoading.value=false}
}
function toggleDetail(id:string){detailId.value=detailId.value===id?'':id;detailRows.value=[];after.value=0;if(detailId.value)loadDetail(true)}
</script>
<template>
<PageHeading index="05 / 复核归档" title="保留校准参数，也保留结论的边界。" note="管理员批准后保存不可变快照，逐对复制原始读数与标记。CSV按分页流式导出全部明细，旧批次与旧报告仍按原快照读取。"/>
<Notice :message="error"/>
<div class="two-col">
 <section>
  <h2>偏倚复核</h2>
  <article v-for="r in reviews.items.value" :key="r.id" class="review-row">
   <StatusPill :status="r.state"/>
   <p>{{r.action}}</p><small>{{r.reviewer||'等待管理员复核'}}</small>
   <div v-if="isAdmin()" class="actions">
    <button v-if="r.state==='submitted'" @click="approve(r.id)" :disabled="busy">批准偏倚复核</button>
    <button v-if="r.state==='approved'" class="secondary" @click="publish(r.id)" :disabled="busy">生成校准快照</button>
   </div>
  </article>
 </section>
 <section>
  <h2>批准底稿</h2>
  <article v-for="r in reports.items.value" :key="r.id" class="report-row">
   <p class="eyebrow">APPROVED COMPARISON</p>
   <h3>{{r.title}}</h3>
   <p>{{r.snapshot.result.n}}组 · {{r.snapshot.result.unit}} · {{r.snapshot.reviewer}} · 归档明细 {{r.snapshot.result.points_in_report??r.snapshot.result.n}} 行</p>
   <div class="actions">
    <button @click="download(r.id)">下载校准 CSV ↓</button>
    <button class="secondary" @click="expanded=expanded===r.id?'':r.id">查看参数快照</button>
    <button class="secondary" @click="toggleDetail(r.id)">归档明细分页</button>
   </div>
   <CalibrationMetrics v-if="expanded===r.id" :result="r.snapshot.result"/>
   <template v-if="detailId===r.id">
    <Notice :message="detailError"/>
    <PairTable :rows="detailRows"/>
    <div class="pager">
     <small>已载入 {{detailRows.length}} / {{total}} 行</small>
     <button v-if="after!==null" class="secondary" :disabled="detailLoading" @click="loadDetail(false)">继续加载 100 行 ↓</button>
    </div>
   </template>
  </article>
 </section>
</div>
</template>
