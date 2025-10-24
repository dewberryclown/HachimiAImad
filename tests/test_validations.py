import pytest,sys,pathlib
from fastapi import HTTPException
sys.path.append(str(pathlib.Path(__file__).parent.parent))
from app.api.validators import validate_bpm
def test_validate_bpm_ok():
    for v in (40, 120, 300):
        validate_bpm(v)
        
@pytest.mark.parametrize("val", [-1, 0, 39, 301, 1000])
def test_validate_bpm_out_of_range(val):
    with pytest.raises(HTTPException) as ei:
        validate_bpm(val)
    assert ei.value.status_code == 422

#测试validate_bpm对于非整数类型的处理
@pytest.mark.parametrize("val", ["abc", 12.3, None, {}, {}])
def test_validate_bpm_not_int(val):
    with pytest.raises(HTTPException) as ei:
        validate_bpm(val)
    assert ei.value.status_code == 422