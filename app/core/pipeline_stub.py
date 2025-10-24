import os,wave,struct,time
from typing import Dict, Any, Callable, Optional
from app.core.storage import stage_dir,file_url,record_stage_artifacts,mark_stage_skipped,write_result

STEPS = ["separate", "midi", "lyrics", "synthesize", "preview"]

def _write_silence_wav(dst_path: str, seconds: float =1.0, sr: int =16000) -> None:
    n_frames = int(seconds *sr)
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with wave.open(dst_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        silence = struct.pack("<h",0)
        for _ in range(n_frames):
            wf.writeframesraw(silence)
            
def run_pipeline_stub(job_id: str, in_path: str, bpm: int, on_step: Optional[Callable[[str, int], None]]= None):
    #分离产物
    if on_step: on_step("separate", 1)
    voc = os.path.join(stage_dir(job_id, "separate"), "vocals.wav")
    acc = os.path.join(stage_dir(job_id, "separate"), "accompaniment.wav")
    _write_silence_wav(voc, 1.0)
    _write_silence_wav(acc, 1.0)
    record_stage_artifacts(job_id, "separate",{
        "vocals.wav": file_url(job_id, "separate", "vocals.wav"),
        "accompaniment.wav": file_url(job_id, "separate", "accompaniment.wav"),
    })
    
    if on_step: on_step("midi",2)
    time.sleep(0.2)
    
    if on_step: on_step("lyrics", 3)
    time.sleep(0.2)
    
    if on_step: on_step("synthesize", 4)
    syn_dir = stage_dir(job_id, "synth")
    vocal = os.path.join(syn_dir, "vocal.wav")
    full = os.path.join(syn_dir, "fullmix.wav")
    _write_silence_wav(vocal, 1.0)
    _write_silence_wav(full, 1.0)
    record_stage_artifacts(job_id, "synth", {
        "vocal.wav": file_url(job_id, "synth", "vocal.wav"),
        "fullmix.wav": file_url(job_id, "synth", "fullmix.wav"),
    })
    
    if on_step: on_step("preview", 5)
    prv = os.path.join(stage_dir(job_id, "preview"), "preview.wav")
    _write_silence_wav(prv, 0.5)
    
    payload = {
        "job_id": job_id,
        "bpm_used": int(bpm),
        "steps": STEPS,
        "outputs": {
            "result_path": full,
            "preview_path": prv,
        },
        "urls":{
            "result_url": file_url(job_id, "synth", "fullmix.wav"),
            "preview_url": file_url(job_id, "preview", "preview.wav")
        },
    }
    write_result(job_id, payload)
    return payload

def _lastest_upload_path(project_id: str) -> Optional[str]:
    up = stage_dir(project_id, "uploads")
    files = [f for f in os.listdir(up) if os.path.isfile(os.path.join(up, f))]
    if not files:
        return None
    files.sort(reverse=True)
    return os.path.join(up, files[0])

def stub_separate(project_id: str, bpm: int, allow_missing: bool = False) -> Dict[str, Any]:
    src = _lastest_upload_path(project_id)
    if not src:
        if allow_missing:
            mark_stage_skipped(project_id, "separate")
            return {"ok": True, "skipped": True}
        raise FileNotFoundError("missing input audio")
    out_dir = stage_dir(project_id, "separate")
    vocals = os.path.join(out_dir, "vocals.wav")
    accomp = os.path.join(out_dir, "accompaniment.wav")
    _write_silence_wav(vocals, seconds=1.0)
    _write_silence_wav(accomp, seconds=1.0)
    files = {
        "vocals.wav": file_url(project_id, "separate","vocals.wav"),
        "accompaniment.wav": file_url(project_id,"separate", "accompaniment.wav"),
    }
    record_stage_artifacts(project_id,"separate",files)
    return{"ok":True, **files}

def stub_synthesize(project_id:str, fmt:str="wav", allow_missing:bool = False) -> Dict[str,Any]:
    #无依赖时可以跳过
    out_dir = stage_dir(project_id, "synth")
    vocal = os.path.join(out_dir, f"vocal.{fmt}")
    full = os.path.join(out_dir, f"fullmix.{fmt}")
    _write_silence_wav(vocal if fmt=="wav" else vocal.replace(f".{fmt}",".wav"), seconds=1.0)
    _write_silence_wav(full if fmt=="wav" else vocal.replace(f".{fmt}",".wav"), seconds=1.0)
    files = {
        os.path.basename(vocal):file_url(project_id,"synth",os.path.basename(vocal)),
        os.path.basename(full):file_url(project_id, "synth", os.path.basename(full)),
    }
    record_stage_artifacts(project_id,"synth",files)
    return {"ok":True, "vocal_url":files[os.path.basename(vocal)],"fullmix_url":files[os.path.basename(full)]}
