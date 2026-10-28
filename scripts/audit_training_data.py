"""Read-only profile of the supplied legacy CSV; never emits source sentences.

This audits data quality only. It neither reconstructs the original FinBERT
training split nor turns training data into an independent evaluation set.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path


def profile(path):
    rows = list(csv.reader(path.open(encoding='ISO-8859-1')))
    valid = [row for row in rows if len(row) == 2]
    text_labels = defaultdict(set)
    for label, text in valid:
        text_labels[text].add(label)
    return {
        'dataset': str(path),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'encoding': 'ISO-8859-1 (as used in ModelSelection.ipynb)',
        'rows': len(rows),
        'invalid_column_count_rows': len(rows) - len(valid),
        'class_counts': dict(sorted(Counter(row[0] for row in valid).items())),
        'empty_text_rows': sum(not row[1].strip() for row in valid),
        'exact_duplicate_rows': len(valid) - len(set(tuple(row) for row in valid)),
        'unique_texts': len(text_labels),
        'repeated_text_rows': len(valid) - len(text_labels),
        'texts_with_conflicting_labels': sum(len(labels) > 1 for labels in text_labels.values()),
        'limitations': [
            'No source/license/annotator metadata is present in the two-column CSV.',
            'Duplicates and conflicting labels can invalidate random-row evaluation.',
            'The original FinBERT split and served-checkpoint linkage are not established by this profile.',
            'This is legacy training material, not untouched V2 evaluation data.',
        ],
    }


if __name__ == '__main__':
    print(json.dumps(profile(Path('Data/dataset.csv')), indent=2, sort_keys=True))
