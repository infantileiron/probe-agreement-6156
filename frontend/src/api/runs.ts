import {request} from "./client";
import type {Page,Point,SamplePayload} from "../types/domain";
export const fetchRuns=()=>request("/runs");
export const fetchRunPoints=(id:string,after=0,limit=100,outside?:boolean)=>request<Page<Point>>(`/runs/${id}/points?after=${after}&limit=${limit}`+(outside===undefined?"":`&outside=${outside}`));
export const fetchRunSample=(id:string)=>request<SamplePayload>(`/runs/${id}/sample`);
export const createRuns=(body:unknown)=>request("/runs","POST",body);
