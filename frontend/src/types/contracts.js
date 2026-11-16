/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,result:Object,approved:boolean,computation_id:?number,is_leader:boolean,waiting:boolean,reuse_source:string,creator:?{id:number,name:string,email:string,role:string}}} AnalysisJob */
/** @typedef {{id:number,share_key:string,rule_version:string,status:string,generation:number,stop_requested:boolean,result:Object,error:string,waiting_count:number,waiters:Array}} SharedComputation */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean}} ReportSchedule */
export {};
