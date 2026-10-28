"""CLI: engineering diagnostics and explicit, currently incomplete full-release gate."""
import argparse
import json
from pathlib import Path
from evaluation.suite import run_suite


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--engine',choices=['baseline','finbert'],default='baseline')
    parser.add_argument('--split',choices=['development','heldout'],default='heldout')
    parser.add_argument('--scope',choices=['engineering','full-release'],default='engineering')
    parser.add_argument('--inject-fault',choices=['invalid-citation','lookahead-fill'])
    parser.add_argument('--output',default='runtime/evaluation/latest.json')
    args=parser.parse_args()
    report=run_suite(args.engine,args.split,args.inject_fault)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    passed=report['engineering_pass'] if args.scope=='engineering' else report['full_release_pass']
    print(json.dumps({'scope':args.scope,'passed':passed,'metrics':report['metrics'],'gate_failures':report['gate_failures'],
        'release_blockers':report['release_blockers'],'artifact':str(path)},indent=2))
    return 0 if passed else 1


if __name__=='__main__': raise SystemExit(main())
