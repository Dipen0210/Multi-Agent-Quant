"""Isolated actual local inference. stdin/stdout JSON; never executes supplied text."""
import contextlib
import json
import sys


def infer(texts):
    import torch
    from transformers import AutoConfig, AutoTokenizer, AutoModelForSequenceClassification
    model_id='Dipen0210/finbert-finetuned'
    config=AutoConfig.from_pretrained(model_id,local_files_only=True)
    tokenizer=AutoTokenizer.from_pretrained(model_id,local_files_only=True)
    model=AutoModelForSequenceClassification.from_pretrained(model_id,local_files_only=True)
    model.eval()
    labels={int(k):v.lower() for k,v in config.id2label.items()}
    if set(labels.values()) != {'positive','negative','neutral'}:
        raise ValueError('Unexpected label mapping')
    results=[];token_count=0
    for offset in range(0,len(texts),8):
        batch=texts[offset:offset+8]
        tokens=tokenizer(batch,return_tensors='pt',padding=True,truncation=True,max_length=512)
        token_count+=int(tokens['attention_mask'].sum().item())
        with torch.no_grad(): probabilities=model(**tokens).logits.softmax(-1).tolist()
        results.extend([{labels[i]:float(p) for i,p in enumerate(row)} for row in probabilities])
    return {'probabilities':results,'model_id':model_id,'revision':getattr(config,'_commit_hash',None),
            'parameters':{'device':'cpu','max_tokens':512,'batch_size':8},'token_usage':token_count,'cost':None,
            'cost_note':'Local compute cost not measured; no remote API usage',
            'calibrated':False,'preprocessing':'entity-sentence-v1; tokenizer truncation to 512 tokens'}


if __name__=='__main__':
    try:
        payload=json.load(sys.stdin)
        texts=payload['texts']
        if not isinstance(texts,list) or len(texts)>100 or any(not isinstance(t,str) or len(t)>10000 for t in texts):
            raise ValueError('Inference input budget exceeded')
        with contextlib.redirect_stdout(sys.stderr): result=infer(texts)
        print(json.dumps({'status':'completed',**result},allow_nan=False))
    except Exception as exc:
        # Exception values can contain provider or filesystem details. Store the class only.
        print(json.dumps({'status':'failed','error_type':type(exc).__name__,'message':'Local model inference unavailable or invalid'}))
        sys.exit(1)
