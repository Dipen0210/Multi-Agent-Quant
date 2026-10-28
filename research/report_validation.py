"""Validate report claims against authoritative local evidence and configuration."""
from research.configuration import Configuration
from research.outputs import QuantitativeResult
from research.reports import ResearchReport


def validate_report_sources(store, raw, expected_run):
    # Import at call time: workflow also invokes this boundary before persistence.
    from research.workflow import quantitative, verify_evidence

    report=ResearchReport.model_validate(raw)
    if (report.run_id!=expected_run['id'] or report.configuration_id!=expected_run['configuration_id']
            or report.snapshot.id!=expected_run['snapshot_id'] or report.question!=expected_run['request']['question']):
        raise ValueError('Report does not match the initiating research request')
    snapshot=store.get_snapshot(report.snapshot.id)
    if any(raw['snapshot'][key]!=snapshot[key] for key in ('request','manifest')):
        raise ValueError('Report snapshot differs from the stored frozen snapshot')
    verify_evidence(store,snapshot,raw['sentiments'])
    expected_quant=quantitative(store,snapshot)
    with store.connect() as c:
        row=c.execute('SELECT data FROM configurations WHERE id=?',(report.configuration_id,)).fetchone()
    if not row: raise ValueError('Missing report configuration')
    configuration=Configuration.model_validate_json(row['data'])
    for instrument,finding in report.findings.items():
        if finding.quantitative.model_dump()!=QuantitativeResult.model_validate(expected_quant[instrument]).model_dump():
            raise ValueError('Numerical finding differs from its authoritative market inputs')
        if finding.research_signal.policy!=configuration.policy:
            raise ValueError('Signal policy differs from the frozen run configuration')
    return raw
