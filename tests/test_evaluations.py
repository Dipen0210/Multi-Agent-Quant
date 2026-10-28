import unittest
from evaluation.suite import run_suite, classification_metrics


class EvaluationTests(unittest.TestCase):
    def test_engineering_gates_and_honest_release_status(self):
        report=run_suite()
        self.assertTrue(report['engineering_pass'],report['gate_failures'])
        self.assertFalse(report['full_release_pass'])
        self.assertIn('Human-reviewed semantic cases pending',report['release_blockers'])
        self.assertEqual(report['metrics']['safety_pass_fraction'],1)
        self.assertIsNone(report['metrics']['cost'])

    def test_injected_verifier_regression_blocks_release(self):
        report=run_suite(inject_fault='invalid-citation')
        self.assertFalse(report['engineering_pass'])
        self.assertIn('invalid_citation_rejected',report['gate_failures'])
        restored=run_suite()
        self.assertTrue(restored['engineering_pass'])

    def test_metrics_count_abstentions_and_class_imbalance(self):
        metrics=classification_metrics(['positive','positive','negative'],['positive','uncertain','negative'])
        self.assertAlmostEqual(metrics['accuracy'],2/3)
        self.assertEqual(metrics['class_balance']['positive'],2)
        self.assertEqual(metrics['per_class']['positive']['recall'],.5)

    def test_lookahead_mutation_blocks_release(self):
        report=run_suite(inject_fault='lookahead-fill')
        self.assertFalse(report['engineering_pass'])
        self.assertIn('lookahead_fill_rejected',report['gate_failures'])
