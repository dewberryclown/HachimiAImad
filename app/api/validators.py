from fastapi import HTTPException

def validate_bpm(bpm: int) -> None:
    try:
        b = int(bpm)
    except Exception:
        raise HTTPException(status_code=422, detail="bpm 必须是整数")
    if b < 40 or b > 300:
        raise HTTPException(status_code=422, detail="bpm 超出合理范围(40-300)")
#验证输入bpm是否有效