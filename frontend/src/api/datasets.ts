import {request,uploadCsv} from "./client";
import type {DatasetPair,Page} from "../types/domain";
export const fetchDatasets=()=>request("/datasets");
export const fetchDatasetPairs=(id:string,after=0,limit=100)=>request<Page<DatasetPair>>(`/datasets/${id}/pairs?after=${after}&limit=${limit}`);
export const createDatasets=(body:unknown)=>request("/datasets","POST",body);
export const importDataset=(file:File,meta:{name:string;unit:string;description:string})=>uploadCsv("/datasets/import",file,{name:meta.name,x_unit:meta.unit,y_unit:meta.unit,description:meta.description});
