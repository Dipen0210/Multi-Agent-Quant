"""Read validated evaluation records without accepting damaged status summaries."""
from datetime import datetime
import json
from evaluation.contracts import EvaluationResult, StudyIntegrityError


def get_evaluation(store,ident):
    with store.connect() as c:
        row=c.execute('SELECT * FROM evaluation_runs WHERE id=?',(ident,)).fetchone()
    if not row: raise StudyIntegrityError('Referenced evaluation is missing')
    try:
        raw=json.loads(row['result'])
        if 'id' in raw: raise ValueError('Evaluation payload cannot override its stored identity')
        result=EvaluationResult.model_validate({'id':row['id'],**raw})
        if (row['dataset_hash']!=result.dataset_hash
                or datetime.fromisoformat(row['created_at'])!=result.created_at
                or row['status']!=('passed' if result.engineering_pass else 'failed')
                or json.loads(row['configuration'])!={'engine':result.engine,'split':result.split,'application_hash':result.application_hash}):
            raise ValueError('Evaluation envelope differs from result')
    except (ValueError,TypeError) as exc:
        raise StudyIntegrityError('Stored evaluation failed validation') from exc
    return {'id':row['id'],**raw}
