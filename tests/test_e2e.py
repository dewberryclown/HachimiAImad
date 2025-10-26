import io,os,wave,time,json,pytest,pathlib,sys
from fastapi.testclient import TestClient
sys.path.append(str(pathlib.Path(__file__).parent.parent))
from app.main import app
from app.core.config import settings

os.environ["CELERY_EAGER"] = "1"
os.environ["REDIS_URL"] = "memory://"

@pytest.fixture(autouse=True)
def _force_eager_and_paths(tmp_path, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CELERY_EAGER", 1, raising=False)
    monkeypatch.setattr(settings, "REDIS_URL", "memory://", raising=False)
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path / "tmp_hachimi"), raising=False)
    monkeypatch.setattr(settings, "PUBLISH_DIR", str(tmp_path / "publish"), raising=False)

@pytest.fixture(autouse=True)
def _isolate_tmp(tmp_path, monkeypatch):
    #猴子补丁重定向临时文件目录和发布目录到pytest临时路径
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path/"tmp_hachimi"))
    monkeypatch.setattr(settings, "PUBLISH_DIR", str(tmp_path/"publish"))
    #开启celery即使执行模式
    monkeypatch.setattr(settings, "CELERY_EAGER", 1)
    yield
    
def _make_silence_wav(seconds=0.2, sr=16000):
    buf = io.BytesIO()#创建二进制文件对象
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        #写入静音数据
        wf.writeframes(b"\x00\x00" * int(seconds*sr))
    buf.seek(0)
    return buf

def test_full_pipeline_and_publish():
    client = TestClient(app)#创建fastapi测试客户端
    audio = _make_silence_wav()
    files = {"file": ("a.wav", audio, "audio/wav")}
    data = {"bpm": "120", "project_name": "demo", "pen_name": "alice"}
    r = client.post("/hachimi_ai_mad/tasks/process", files=files, data=data)
    assert r.status_code == 201, r.text
    payload = r.json()
    job_id = payload["job_id"]
    #轮询任务状态(共3s)
    for _ in range(30):
        s = client.get(f"/hachimi_ai_mad/tasks/{job_id}/status").json()
        if s["status"] in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(0.1)
    assert s["status"] == "SUCCEEDED"
    #下载结果
    r = client.get(f"/hachimi_ai_mad/tasks/{job_id}/download")
    assert r.status_code == 200
    result = r.json()
    assert result["urls"]["result_url"].startswith("/hachimi_ai_mad/projects/")
    assert result["urls"]["preview_url"].startswith("/hachimi_ai_mad/projects/")
    #发布任务
    r = client.post(f"/hachimi_ai_mad/tasks/{job_id}/publish")
    assert r.status_code == 200
    pub = r.json()
    public_id = pub["public_id"]
    #验证展示区访问
    assert client.get("/hachimi_ai_mad/showcase").status_code ==200
    assert client.get(f"/hachimi_ai_mad/showcase/{public_id}/preview").status_code == 200
    assert client.get(f"/hachimi_ai_mad/showcase/{public_id}/result").status_code == 200
    #验证项目产物直链
    arts = client.get(f"/hachimi_ai_mad/projects/{job_id}/artifacts").json()
    assert "synth" in arts["stages"]
    #随机访问验证
    any_file = next(iter(arts["stages"]["synth"]["files"].values()))
    assert client.get(any_file).status_code == 200
    
def test_stage_retry_and_uploads():
    client = TestClient(app)
    project_id = "p1"
    #上传MIDI
    midi = io.BytesIO(b"MThd\x00\x00\x00\x06\x00\x01\x00\x01\x00\x60")
    files = {"midi_file": ("a.mid", midi, "audio/midi")}
    r = client.post("/hachimi_ai_mad/stages/midi/upload", data={"project_id": project_id, "quantize": "true"}, files=files)
    assert r.status_code == 200
    #填词上传
    phrase = io.BytesIO(json.dumps({"phrases":[]}).encode("utf-8"))
    files = {"phrases_json": ("phrases.json", phrase, "application/json")}
    r = client.post("/hachimi_ai_mad/stages/lyrics/upload", data={"project_id": project_id}, files=files)
    assert r.status_code == 200
    #重试分离
    r = client.post("/hachimi_ai_mad/stages/separate/retry", data={"project_id": project_id, "allow_missing": "true"})
    assert r.status_code == 200
    #合成重试
    r = client.post("/hachimi_ai_mad/stages/synthesize/retry", json={"project_id": project_id, "format": "wav", "allow_missing": True})
    assert r.status_code == 200
    #验证合成产物
    arts = client.get(f"/hachimi_ai_mad/projects/{project_id}/artifacts").json()
    assert "synth" in arts["stages"]
    
def test_admin_feature_requires_secret(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_SECRET", "s3cr3t")
    client = TestClient(app)

    # 无密钥 403
    r = client.post("/hachimi_ai_mad/admin/feature-project", json={"project_id":"p1","admin_secret":""})
    assert r.status_code == 403

    # 正确密钥 200
    r = client.post("/hachimi_ai_mad/admin/feature-project", json={"project_id":"p1","admin_secret":"s3cr3t"})
    assert r.status_code == 200
    assert r.json().get("ok") is True
    
