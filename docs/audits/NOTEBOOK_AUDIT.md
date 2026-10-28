# Supplied notebook audit — 2026-10-28

The user directed inspection of both notebooks. Originals were read as JSON, not executed or modified. Saved outputs are historical artifacts, not newly reproduced training or return results. Cell numbers below are one-based, including Markdown cells.

| Artifact | SHA-256 | Role |
|---|---|---|
| `ModelSelection.ipynb` | `1054810194f6de23c002553a02a4f3a461048452f0d4617642d5d2703a428707` | Classical model comparison and FinBERT fine-tuning |
| `tradingStrategy.ipynb` | `095181addbe82e7f5b848e0ac5d3312084f7e4b46d51614bd0175547ba6e3998` | News/indicator signal prototype and legacy simulation |
| `Data/dataset.csv` | `0fbee3502f0130db1798bce8479aed852847d7a98b80ed6941ebf489d77d2fb1` | Available two-column legacy labeled text |

## Model-selection evidence

- Cell 5 reads `dataset.csv` using ISO-8859-1. Saved output reports 10,688 rows: 6,009 neutral, 3,215 positive, 1,464 negative. The available `Data/dataset.csv` matches these counts; matching counts alone do not prove exact original training bytes.
- Cells 23–26 create a random 80/20 Hugging Face dataset split and load `yiyanghkust/finbert-tone` tokenizer/classifier. FinBERT uses the original `text` column; the earlier cleaned-text column is for classical models. No split seed or stratification is specified for the Hugging Face split, and the original split indices are not saved.
- The labels are explicitly set to negative=0, neutral=1, positive=2. Cell 28 specifies 10 epochs, train/evaluation batch size 16, learning rate 0.00002 and weight decay 0.01. Cell 35 saves to `./my-finbert-finetuned`. No Hub upload or served-checkpoint manifest is present.
- Cell 33's stored output reports rounded accuracy 0.88 on 2,138 test rows. This has **not** been reproduced, is not independent V2 acceptance evidence, and must not be used as real-world accuracy or profitability proof.
- Read-only profiling found 4,121 redundant exact `(label, text)` rows; 6,051 distinct texts; and 516 texts assigned multiple labels. These are data-quality issues, not evidence that any particular label is correct. Original labels remain preserved.
- A separate diagnostic using random state 42 and an 80/20 row split found 1,453 of 2,138 test rows with identical text in the training split. This is not reconstruction of the notebook's unseeded FinBERT split. It demonstrates why random-row accuracy is unsafe for this CSV. No duplicate removal, relabeling, retraining or checkpoint replacement was performed.

Reproduce the source-data profile without exposing sentences:

```sh
venv/bin/python -m scripts.audit_training_data
```

The captured result is `docs/audits/TRAINING_DATA_PROFILE.json`. Legacy training data must not be repurposed as an untouched V2 test set. A future training experiment needs documented data rights, reviewed conflicting labels, grouped/deduplicated partitions fixed before training, separate validation/test sets and a checkpoint manifest.

## Strategy notebook findings

| Severity | Cells | Observed code / implication | V2 disposition |
|---|---|---|---|
| Critical | 35 | `get_stock_data` searches offsets from -5 to +5 and returns the first available price. A fill labeled as next-day execution can actually use a pre-signal price. | Original excluded from acceptance; `research/simulation.py` requires execution strictly after the decision. Look-ahead mutation tests must reject the regression. |
| Critical | 35 | One global holding count is used across tickers; the SELL branch does not require the current ticker to equal `buy_ticker`. Final marking uses the last fetched close. | Original accounting is invalid for multi-ticker results. V2 experiments use explicit instrument-specific simulations and reconciled cash/equity. |
| High | 29 | On disagreement, aggregation averages unsigned classifier confidence; a confidently negative article can push the mean above the BUY threshold. The SELL threshold cannot be met by nonnegative probabilities. | V2 uses directional sentiment and explicit conflicting/no-signal statuses. |
| High | 14 | Every unrecognized headline is assigned to SPY; substring matching returns only the first recognized company. | V2 requires supported instruments and explicit entity-specific evidence; missing identity abstains. |
| High | 9, 23 | News retains only calendar date/headline, discarding exact publication time, URL and availability history. Daily indicators include the news day's close without an explicit decision-time contract. | V2 preserves exact source versions/timestamps and cutoff rules. Historical metadata gaps are disclosed as approximations. |
| High | 9 | A nonempty literal provider API key is embedded in source. Its value was omitted from inspection output. | The local original is preserved; `.gitignore` excludes this untracked notebook, and `.dockerignore` excludes notebooks. No key was used or exported. Sanitization/credential rotation is separate from this read-only audit. |
| Medium | 31, 35 | Calendar handling only checks weekends; no fees, slippage, liquidity or adjustment contract in the original simulation. | V2 uses XNYS sessions and explicit friction, liquidity and adjustment assumptions. |

`tradingStrategy.ipynb` cell 7 loads `/content/drive/MyDrive/my-finbert-finetuned`, consistent with the other notebook's output directory name but without a checksum linking either artifact to the served Hub revision. It adds no dataset origin or license evidence. Its saved return summary is not cited as valid performance.

## Remaining provenance evidence

Dataset publisher/source and license; permission/license for base and derived weights; pinned training input and split identifiers; export/upload linkage to served revision; model knowledge cutoff if available. User guidance to inspect these notebooks is not approval of provisional semantic labels or release gates.
