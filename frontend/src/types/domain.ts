export type Role="admin"|"analyst"|"viewer";
export interface User{email:string;role:Role}
export interface Entity{id:string;created_at:string;[key:string]:any}
export interface DatasetPair{pair_id:string;range_label:string;x:number;y:number;id?:number}
export interface Point{pair_id:string;range_label:string;x:number;y:number;mean:number;difference:number;fitted_y:number;residual_y?:number;outside_loa:boolean;outside_tolerance:boolean}
export type Row=Pick<Point,"pair_id"|"range_label"|"x"|"y"> & Partial<Pick<Point,"mean"|"difference"|"fitted_y"|"outside_loa"|"outside_tolerance">>
export interface Page<T>{items:T[];next_after:number|null;total:number;after:number;limit:number}
export interface SamplePayload{items:Point[];sample_size:number;n:number;note:string}
export interface RunSummary{id:string;status:string;progress:number;phase:string;error:string;result:any}
