"""Compatibility endpoint. External execution is outside the V2 release."""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post('/trade', summary='External trading disabled')
def place_trade():
    raise HTTPException(status_code=403, detail={
        'code': 'external_execution_disabled',
        'message': 'V2 supports research and internal simulation only.',
    })
