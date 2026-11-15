<script setup lang="ts">
import {computed,onMounted,ref} from 'vue';
import {runs} from '../stores/runs';
import {fetchRunSample} from '../api/runs';
import type {Point,RunSummary} from '../types/domain';
import PageHeading from '../components/common/PageHeading.vue';
import AgreementPlot from '../components/AgreementPlot.vue';
import CalibrationMetrics from '../components/CalibrationMetrics.vue';
const sample=ref<Point[]>([]);
onMounted(async()=>{
 await runs.load();
 const run=runs.items.value.find((r:any)=>r.id==='demo-run')||runs.items.value.find((r:any)=>r.status==='completed');
 if(run)try{sample.value=(await fetchRunSample(run.id)).items}catch{sample.value=[]}
});
const run=computed<RunSummary|undefined>(()=>(runs.items.value.find((r:any)=>r.id==='demo-run')||runs.items.value.find((r:any)=>r.status==='completed')) as RunSummary|undefined);
const result=computed(()=>run.value?.result);
</script>
<template>
<PageHeading index="00 / 校准总览" title="一条校准线，还需要一张差值图。" note="两侧探头均有误差。用Deming回归校准关系，再用Bland–Altman检视偏倚、量级趋势及界限外配对。图表只画有界抽样，统计与计数使用全部读数。"/>
<template v-if="result">
 <CalibrationMetrics :result="result"/>
 <div class="overview-layout">
  <section>
   <div class="section-heading"><h2>双探头关系 · {{result.unit}}</h2><a href="#/results">查看完整运行底稿 ↗</a></div>
   <AgreementPlot :points="sample" :result="result" mode="deming"/>
   <div class="method-ribbon"><b>{{result.n}} 组</b><span>{{result.x_serial}} ↔ {{result.y_serial}}</span><span>图表抽样 {{result.sample_size}} 组</span></div>
  </section>
  <aside class="field-note">
   <p class="eyebrow">AGREEMENT CHECK</p>
   <h2>差值，是否随量级变化？</h2>
   <AgreementPlot :points="sample" :result="result" mode="ba"/>
   <p>一致性界限是差值分布的近似覆盖范围，不是偏倚的置信区间。界限内也不直接表示设备可互换。</p>
   <p>{{result.sample_note}}</p>
  </aside>
 </div>
 <section class="workflow-strip">
  <div><b>01 / 配对</b><h3>同一对象，同一单位</h3><p>坏行或重复编号使整批不可见，可重试。</p></div>
  <div><b>02 / 估计</b><h3>先写明误差比</h3><p>λ=var(y误差)/var(x误差)，不自动猜测。</p></div>
  <div><b>03 / 复核</b><h3>让结论保留边界</h3><p>对照量程、异常配对与现场校准标准。</p></div>
 </section>
</template>
</template>
