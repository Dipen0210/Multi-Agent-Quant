"""Entity-grounded sentiment. Baseline rules are explicit, not a trained-model claim."""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Literal
from pydantic import Field, model_validator, field_validator
from research.contracts import Contract, Document, UNIVERSE, utc

ALIASES={'US:AAPL':r'\b(?:Apple|AAPL)\b','US:MSFT':r'\b(?:Microsoft|MSFT)\b','US:SPY':r'\b(?:SPY|S&P 500)\b'}
POSITIVE=r'\b(?:higher|increased|growth|grew|raised|beat|improved|strong|profit|profits)\b'
NEGATIVE=r'\b(?:lower|declined|decline|cut|missed|loss|losses|weak|fell|decreased)\b'
INJECTION=r'ignore (?:all |previous |prior )?instructions|reveal.{0,30}(?:key|secret|prompt)|execute.{0,20}(?:trade|shell)|system prompt'


class Span(Contract):
    document_id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=10000)

    @model_validator(mode='after')
    def bounds(self):
        if self.end <= self.start or len(self.quote) != self.end-self.start:
            raise ValueError('Invalid evidence span bounds')
        return self


class SentimentResult(Contract):
    instrument_id: str
    document_id: str
    label: Literal['positive','negative','neutral'] | None
    score: float | None = Field(default=None, ge=-1, le=1)
    status: Literal['supported','uncertain','conflicting','insufficient_evidence','failed']
    evidence: list[Span]
    model_version: str
    preprocessing_version: str = 'entity-sentence-v1'
    confidence_method: str = 'none; score is directional sentiment, not probability of returns'
    calibrated: Literal[False] = False
    subject: Literal['company_or_fund'] = 'company_or_fund'
    event_sentiment: str | None = None
    return_hypothesis: str | None = None
    cutoff: datetime
    created_at: datetime = Field(default_factory=lambda:datetime.now(timezone.utc))
    reason: str


    @field_validator('cutoff','created_at')
    @classmethod
    def aware(cls,value): return utc(value)

    @model_validator(mode='after')
    def supported_contract(self):
        if self.status=='supported' and (self.label is None or self.score is None or not self.evidence):
            raise ValueError('Supported sentiment requires a label, score and evidence')
        if self.status!='supported' and self.label is not None:
            raise ValueError('Uncertain or failed sentiment cannot claim a supported label')
        return self


def evidence_spans(record: dict, instrument_id: str):
    data=Document.model_validate(record['data']).model_dump(mode='json'); text=data['content']; spans=[]; ambiguous=False
    if instrument_id not in data['instrument_ids'] or data['entity_status'] != 'resolved':
        return [],'No resolved target identity'
    if data['language'] != 'en': return [],'Unsupported language'
    if re.search(INJECTION,text,re.I): return [],'Source contains instruction-like content; quarantined from sentiment inference'
    # Keep original offsets. Split at punctuation followed by whitespace (not decimal dots).
    for match in re.finditer(r'[^.!?;]+(?:[.!?;]|$)',text):
        quote=match.group().strip()
        if not quote: continue
        start=match.start()+len(match.group())-len(match.group().lstrip())
        targets=[key for key,pattern in ALIASES.items() if re.search(pattern,quote,re.I)]
        if instrument_id not in targets: continue
        if len(targets)>1:
            ambiguous=True
            continue
        if len(quote)>10000:
            ambiguous=True
            continue
        spans.append(Span(document_id=record['id'],start=start,end=start+len(quote),quote=quote))
    if ambiguous: return [],'Comparative or multi-entity sentence requires reviewed attribution'
    return spans, '' if spans else 'No unambiguous target-specific sentence'


def baseline_score(text: str):
    votes=[]
    for pattern,sign in [(POSITIVE,1),(NEGATIVE,-1)]:
        for match in re.finditer(pattern,text,re.I):
            prefix=text[max(0,match.start()-32):match.start()].lower().split()[-3:]
            votes.append(-sign if any(w in {'not','no','never',"didn't","wasn't"} for w in prefix) else sign)
    if 1 in votes and -1 in votes: return 0.0,'conflicting'
    return (sum(votes)/len(votes) if votes else 0.0),'supported'


def analyze_record(record, instrument_id, cutoff, model_version='lexicon-v1', probabilities=None):
    spans,problem=evidence_spans(record,instrument_id)
    common=dict(instrument_id=instrument_id,document_id=record['id'],evidence=spans,
                model_version=model_version,cutoff=cutoff,reason=problem)
    if not spans:
        return SentimentResult(**common,label=None,status='uncertain' if problem.startswith(('Unsupported','Source','Comparative')) else 'insufficient_evidence')
    text=' '.join(s.quote for s in spans)
    baseline,status=baseline_score(text)
    if probabilities is None:
        score=baseline
    else:
        if set(probabilities) != {'positive','negative','neutral'} or any(not isinstance(v,(int,float)) or not 0<=v<=1 for v in probabilities.values()) or abs(sum(probabilities.values())-1)>1e-4:
            raise ValueError('Invalid model probability contract')
        score=probabilities['positive']-probabilities['negative']
    if status=='conflicting':
        common['reason']='Opposing directional language; retained as conflicting evidence'
        label=None
    else:
        label='positive' if score>.15 else 'negative' if score<-.15 else 'neutral'
        common['reason']='Sentiment toward named entity in cited text; not a forecast of returns'
    if '"' in text or '“' in text:
        status='uncertain';common['reason']='Quoted claim; attribution requires review';label=None
    return SentimentResult(**common,label=label,score=score,status=status,
                           event_sentiment='Text may describe an event; no separate event-level attribution model validated.')


def aggregate(results, groups):
    """One vote per independent document group, per instrument; no recency weighting."""
    by_id={r.document_id:r for r in results}
    accepted=[];group_conflict=False
    for group in groups:
        candidates=[by_id[key] for key in group if key in by_id]
        usable=[r for r in candidates if r.status=='supported']
        if len({r.label for r in usable if r.label!='neutral'})>1:
            group_conflict=True
        elif usable: accepted.append(usable[0])
    directional=[r for r in accepted if r.label!='neutral']
    labels={r.label for r in directional}
    conflicts=group_conflict or any(r.status=='conflicting' for r in results) or len(labels)>1
    status='conflicting' if conflicts else 'supported' if accepted else 'insufficient_evidence'
    return {'status':status,'score':sum(r.score for r in accepted)/len(accepted) if accepted else None,
            'independent_sources':len(accepted),'raw_documents':len(results),'directional_sources':len(directional),
            'positive':sum(r.label=='positive' for r in accepted),'negative':sum(r.label=='negative' for r in accepted),
            'excluded_or_uncertain':sum(r.status!='supported' for r in results),
            'policy':'equal weight per duplicate group; uniform recency within snapshot window; no calibrated probability'}
