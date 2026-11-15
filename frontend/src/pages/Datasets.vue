<script setup lang="ts">
import {ref,onMounted,computed} from 'vue';
import {datasets} from '../stores/datasets';
import {fetchDatasetPairs,importDataset} from '../api/datasets';
import {canWrite} from '../stores/auth';
import {useTask} from '../hooks/useTask';
import {units} from '../constants/enums';
import type {Row} from '../types/domain';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import PairTable from '../components/PairTable.vue';

const name=ref(''),unit=ref('kPa'),description=ref(''),file=ref<File|null>(null),text=ref('');
const openId=ref(''),rows=ref<Row[]>([]),after=ref<number|null>(0),total=ref(0),loadingRows=ref(false),rowError=ref('');
const {error,busy,act}=useTask();
onMounted(datasets.load);

async function loadPage(reset:boolean){
 const dataset=datasets.items.value.find((r:any)=>r.id===openId.value);if(!dataset)return;
 loadingRows.value=true;rowError.value='';
 try{
  const page=await fetchDatasetPairs(dataset.id,reset?0:(after.value||0),100);
  rows.value=reset?page.items:rows.value.concat(page.items);
  after.value=page.next_after;total.value=page.total;
 }catch(e){rowError.value=(e as Error).message}finally{loadingRows.value=false}
}
function toggle(id:string){openId.value=openId.value===id?'':id;rows.value=[];after.value=0;if(openId.value)loadPage(true)}

function pick(e:Event){const f=(e.target as HTMLInputElement).files?.[0];file.value=f||null}
function submit(){
 const selected=file.value;
 act(async()=>{
  if(selected)await importDataset(selected,{name:name.value,unit:unit.value,description:description.value});
  else await datasets.create({name:name.value,x_unit:unit.value,y_unit:unit.value,csv_text:text.value,description:description.value});
  name.value='';file.value=null;text.value='';await datasets.load();
 });
}
const largeFile=computed(()=>Boolean(file.value&&file.value.size>2*1024*1024));
</script>
<template>
<PageHeading index="01 / 配对观测" title="把两侧读数，按同一编号放在一起。" note="CSV列pair_id,range_label,x,y；量程low/middle/high。整批导入，任一行坏损或编号重复则整批不可见；底稿明细分页读取，不一次装入内存。"/>
<div class="two-col">
 <section>
  <Notice :message="datasets.error.value"/>
  <article v-for="r in datasets.items.value" :key="r.id" class="dataset-row">
   <button class="record-open" @click="toggle(r.id)">
    <h3>{{r.name}}</h3>
    <p>{{r.pair_count}}组 · X/Y={{r.x_unit}}/{{r.y_unit}} · {{r.description}}</p>
    <span>分页预览全部读数 ↗</span>
   </button>
   <template v-if="openId===r.id">
    <Notice :message="rowError"/>
    <PairTable :rows="rows"/>
    <div class="pager">
     <small>已载入 {{rows.length}} / {{total}} 组</small>
     <button v-if="after!==null" class="secondary" :disabled="loadingRows" @click="loadPage(false)">继续加载 100 组 ↓</button>
    </div>
   </template>
  </article>
 </section>
 <form v-if="canWrite()" class="editor-panel" @submit.prevent="submit">
  <h2>导入配对批次</h2>
  <label>批次名称<input v-model="name" required minlength="2"></label>
  <label>共同单位<select v-model="unit"><option v-for="u in units" :key="u">{{u}}</option></select></label>
  <label>CSV文件<input type="file" accept=".csv,text/csv" @change="pick"></label>
  <label>或粘贴小批量CSV（≤5000行，走JSON导入）<textarea v-model="text" rows="5" placeholder="pair_id,range_label,x,y"></textarea></label>
  <label>采样说明<input v-model="description"></label>
  <p class="field-hint">{{largeFile||text.trim()===''?'大文件按请求体流入数据库，分段提交；内存不随行数增长。':'粘贴的小批量走原有 JSON 接口，仍最多 5000 行。'}}</p>
  <Notice :message="error"/>
  <button :disabled="busy||(!file&&text.trim()==='')">校验并导入整批</button>
 </form>
 <aside v-else class="field-note">只读账号可核查原始读数。导入需要分析师权限。</aside>
</div>
</template>
