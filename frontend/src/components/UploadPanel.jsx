import { useState } from "react";
import { supabase } from "../lib/supabase";

const API = import.meta.env.VITE_API_URL || "";

const STAGES = ["Uploading","Validating","Processing","Generating polygons","Running topology validation","Saving results","Complete"];

export default function UploadPanel({ project, survey, onComplete, onBack }) {
  const [file,setFile]=useState(null), [reference,setReference]=useState(null), [groundTruth,setGroundTruth]=useState(null), [dsm,setDsm]=useState(null);
  const [preview,setPreview]=useState(null), [stage,setStage]=useState(""), [progress,setProgress]=useState(0), [error,setError]=useState("");

  const choose=(f,setter,accept,label)=>{
    if(!f)return;
    if(!accept(f)){setError(label);return;}
    setError(""); setter(f);
    if(f.type.startsWith("image/")) setPreview(URL.createObjectURL(f));
  };

  async function updateSurvey(status, extra={}) {
    if(!survey?.id) return;
    try { await supabase.from("surveys").update({status,...extra}).eq("id",survey.id); } catch {}
  }

  async function analyze() {
    if(!file){setError("Please select the required orthomosaic/drone image.");return;}
    if(!API){setError("VITE_API_URL is not configured. Set it to the deployed FastAPI base URL.");return;}
    setError(""); setProgress(5); setStage("Uploading"); await updateSurvey("uploading");
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if(!session?.access_token) throw new Error("Authentication session expired. Please sign in again.");
      const headers={Authorization:`Bearer ${session.access_token}`};
      const base=API.replace(/\/$/,"");
      const body=new FormData();
      body.append("file",file);
      if(reference)body.append("reference_parcels",reference);
      if(groundTruth)body.append("ground_truth",groundTruth);
      if(dsm)body.append("dsm",dsm);

      const uploadResponse=await fetch(base+`/api/surveys/${survey.id}/upload`,{method:"POST",body,headers});
      const uploadType=uploadResponse.headers.get("content-type")||"";
      const uploadData=uploadType.includes("application/json")?await uploadResponse.json():{error:{message:await uploadResponse.text()}};
      if(!uploadResponse.ok) throw new Error(uploadData?.error?.message||uploadData?.detail||("Upload failed with HTTP "+uploadResponse.status));

      setProgress(20); setStage("Queued"); await updateSurvey("processing");
      const processResponse=await fetch(base+`/api/surveys/${survey.id}/process`,{method:"POST",headers});
      const processData=await processResponse.json().catch(()=>({}));
      if(!processResponse.ok) throw new Error(processData?.error?.message||processData?.detail||("Processing request failed with HTTP "+processResponse.status));

      let statusData=processData;
      for(let attempt=0;attempt<120;attempt++){
        await new Promise(resolve=>setTimeout(resolve,1000));
        const statusResponse=await fetch(base+`/api/surveys/${survey.id}/processing-status`,{headers});
        statusData=await statusResponse.json().catch(()=>({}));
        if(!statusResponse.ok) throw new Error(statusData?.error?.message||statusData?.detail||("Status request failed with HTTP "+statusResponse.status));
        const s=String(statusData.status||"").toUpperCase();
        setStage(statusData.stage||s||"Processing");
        setProgress(typeof statusData.progress==="number"?statusData.progress:Math.min(95,25+attempt));
        if(s==="COMPLETED") break;
        if(s==="FAILED") throw new Error(statusData.error||"AI/GIS processing failed.");
        if(attempt===119) throw new Error("Processing timed out while waiting for the backend job.");
      }

      setProgress(96); setStage("Loading final results");
      const resultResponse=await fetch(base+`/api/surveys/${survey.id}/results`,{headers});
      const resultData=await resultResponse.json().catch(()=>({}));
      if(!resultResponse.ok) throw new Error(resultData?.error?.message||resultData?.detail||("Results request failed with HTTP "+resultResponse.status));
      const payload=resultData.result||resultData;
      await updateSurvey("complete",{source_crs:payload.raster_metadata?.crs||null,source_image_url:payload.original_image_url||uploadData.source_image_url||null});
      setProgress(100); setStage("Complete");
      onComplete({...payload,original_image_url:(payload.original_image_url||uploadData.source_image_url||"").startsWith("http")?(payload.original_image_url||uploadData.source_image_url):base+(payload.original_image_url||uploadData.source_image_url||""),project_id:project?.id,survey_id:survey?.id,project_name:project?.name,survey_name:survey?.name});
    } catch(e) {
      const msg=e instanceof TypeError?"Backend unavailable. Check VITE_API_URL and FastAPI deployment.":e.message||"Processing failed.";
      setError(msg); await updateSurvey("failed"); setStage("");
    }
  }

  return <main className="gov-portal">
    <div className="gov-top-strip"><div>भारत सरकार &nbsp;|&nbsp; Government of India</div><div className="gov-tools"><button type="button" onClick={onBack}>Project Dashboard</button></div></div>
    <header className="gov-header"><div className="gov-brand"><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Government_of_India_logo.svg/120px-Government_of_India_logo.svg.png" alt="Government of India emblem"/><div><div className="gov-hindi">ग्रामीण विकास मंत्रालय</div><div className="gov-title">MINISTRY OF RURAL DEVELOPMENT</div><div className="gov-subtitle">GOVERNMENT OF INDIA</div></div></div><div className="sahinaksha-brand"><strong>SahiNaksha</strong><span>AI-Assisted Cadastral Mapping</span></div></header>
    <div className="gov-notice"><b>Prototype Portal</b> — SIH 2026 demonstration system; not an official Government of India service.</div>
    <section className="gov-content" style={{maxWidth:"1100px",margin:"28px auto",padding:"0 20px"}}>
      <div className="gov-page-title"><span>03 • DATA INGESTION</span><small>{project?.name} / {survey?.name}</small></div>
      <div className="workflow-heading"><span>Survey Upload</span><h2>Upload &amp; Validate Inputs</h2><p>Required orthomosaic plus optional DSM/DTM, reference parcels and ground truth.</p></div>
      <div className="upload-card">
        <label className="file-picker"><input type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" onChange={e=>choose(e.target.files?.[0],setFile,f=>["image/jpeg","image/png"].includes(f.type),"Only JPG/PNG imagery is currently supported by the FastAPI upload endpoint.")}/><span>{file?file.name:"Required — Orthomosaic / Drone Image"}</span></label>
        <label className="file-picker"><input type="file" accept=".json,.geojson" onChange={e=>choose(e.target.files?.[0],setReference,f=>/\.(json|geojson)$/i.test(f.name),"Reference parcel GIS must be GeoJSON.")}/><span>{reference?reference.name:"Optional — Reference Parcel GIS"}</span></label>
        <label className="file-picker"><input type="file" accept=".jpg,.jpeg,.png" onChange={e=>choose(e.target.files?.[0],setDsm,f=>/\.(jpg|jpeg|png)$/i.test(f.name),"DSM/DTM prototype input must currently be aligned JPG/PNG.")}/><span>{dsm?dsm.name:"Optional — DSM / DTM"}</span></label>
        <label className="file-picker"><input type="file" accept=".json,.geojson" onChange={e=>choose(e.target.files?.[0],setGroundTruth,f=>/\.(json|geojson)$/i.test(f.name),"Ground truth must be GeoJSON.")}/><span>{groundTruth?groundTruth.name:"Optional — Ground Truth"}</span></label>
        {preview&&<img className="preview" src={preview} alt="Orthomosaic preview"/>}
        {stage&&<div className="upload-progress" style={{marginTop:"14px"}}><b>{stage}</b><div style={{height:"8px",background:"#e2e8f0",borderRadius:"8px",marginTop:"8px"}}><div style={{width:progress+"%",height:"100%",background:"#176b4d",borderRadius:"8px"}}/></div><small>{progress}%</small></div>}
        {error&&<p className="error">{error}</p>}
        <div className="gov-form-note"><b>Input validation:</b> CRS and spatial alignment are checked by the backend when reference GIS is supplied. Missing/ambiguous CRS is rejected rather than silently invented.</div>
        <button className="primary-button" disabled={!!stage||!file} onClick={analyze}>{stage&&stage!=="Complete"?stage:"Start Processing"}</button>
      </div>
    </section>
  </main>;
}
