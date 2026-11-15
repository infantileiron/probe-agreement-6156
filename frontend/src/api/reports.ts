import {request} from "./client";
import type {Page,Point} from "../types/domain";
export const fetchReports=()=>request("/reports");
export const fetchReportPoints=(id:string,after=0,limit=100)=>request<Page<Point>>(`/reports/${id}/points?after=${after}&limit=${limit}`);
export const createReports=(body:unknown)=>request("/reports","POST",body);
