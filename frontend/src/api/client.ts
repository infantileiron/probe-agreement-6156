
export async function request<T=any>(path:string,method="GET",body?:unknown):Promise<T>{
 const token=localStorage.getItem("probe-token");const response=await fetch("/api"+path,{method,headers:{"Content-Type":"application/json",...(token?{Authorization:"Bearer "+token}:{})},body:body===undefined?undefined:JSON.stringify(body)});
 if(!response.ok){let message="请求失败";try{const error=await response.json();message=typeof error.detail==="string"?error.detail:JSON.stringify(error.detail)}catch{};throw new Error(message)}return response.json();
}

export async function downloadCsv(id:string,filename="probe-calibration.csv"){
 // Streams to a blob without buffering the whole archive in a JS string first.
 const r=await fetch("/api/reports/"+id+"/csv",{headers:{Authorization:"Bearer "+localStorage.getItem("probe-token")}});
 if(!r.ok)throw new Error("下载失败");
 const a=document.createElement("a");a.href=URL.createObjectURL(await r.blob());a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}

export async function uploadCsv(path:string,file:File,query:Record<string,string>):Promise<any>{
 const params=new URLSearchParams(query).toString();
 const token=localStorage.getItem("probe-token");
 const r=await fetch("/api"+path+(params?"?"+params:""),{method:"POST",headers:{"Content-Type":"text/csv",...(token?{Authorization:"Bearer "+token}:{})},body:file});
 if(!r.ok){let message="导入失败";try{const error=await r.json();message=typeof error.detail==="string"?error.detail:JSON.stringify(error.detail)}catch{};throw new Error(message)}
 return r.json();
}
