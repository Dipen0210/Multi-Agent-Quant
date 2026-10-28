"""Cancellable and time-bounded subprocess inference with no network access by design."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


class Cancelled(RuntimeError): pass


def local_finbert(texts, cancelled=lambda:False, timeout=60):
    env={key:value for key,value in os.environ.items() if key in {'PATH','HOME','LANG','TMPDIR','SYSTEMROOT'}}
    env.update({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'2'})
    process=subprocess.Popen([sys.executable,'-m','research.inference_worker'],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=env,cwd=str(Path(__file__).parents[1]))
    started=time.monotonic(); sent=False
    try:
        while True:
            if cancelled(): raise Cancelled('Research run cancelled')
            if time.monotonic()-started>timeout: raise TimeoutError('Local inference exceeded its time budget')
            try:
                output,_=process.communicate(json.dumps({'texts':texts}) if not sent else None,timeout=.1)
                break
            except subprocess.TimeoutExpired:
                sent=True
        if process.returncode:
            raise RuntimeError('Local inference failed; weights/tokenizer or valid model output unavailable')
        result=json.loads(output)
        if result.get('status')!='completed' or len(result.get('probabilities',[]))!=len(texts):
            raise ValueError('Invalid inference response contract')
        return result
    finally:
        if process.poll() is None: process.kill()
        process.wait()
        for stream in (process.stdin,process.stdout):
            if stream is not None and not stream.closed: stream.close()
