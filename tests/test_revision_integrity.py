"""Offline regression checks for the corrected public analysis controls.

Run: python -m unittest discover -s tests -v
Requires numpy and pandas for the cell-origin screen, but no LLM/API or atlas.
"""
import csv
import gzip
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = load('execution_policy', 'personaai/rag/backend/agent/execution_policy.py')
comparison = load('comparison_labels', 'analysis/comparison_labels.py')
grading = load('evidence_grading', 'personaai/scrna_mcp/sc_analysis_mcp/sc_analysis_mcp/evidence_grading.py')
genetics = load('creld2', 'analysis/creld2_human_genetics/scripts/run_creld2_pqtl_followup.py')


class RetrievalBoundaryTests(unittest.TestCase):
    def test_new_request_resets_audit_history_and_records_configuration(self):
        env = {'OPENROUTER_MODEL': 'test/model', 'MAX_SEARCH_ATTEMPTS': '3'}
        first = policy.new_run_audit(env)
        first['evaluation_history'].append({'completeness': .8})
        second = policy.new_run_audit(env)
        self.assertEqual(second['evaluation_history'], [])
        self.assertEqual(second['human_decision_count'], 0)
        self.assertNotEqual(first['audit_run_id'], second['audit_run_id'])
        self.assertEqual(second['execution_config']['configured_model'], 'test/model')
        self.assertTrue(second['execution_config']['corpus_only'])

    def test_default_does_not_construct_external_tools_even_with_a_key(self):
        def prohibited(*args, **kwargs):
            self.fail('An external/general-purpose tool was constructed')
        env = {'TAVILY_API_KEY': 'synthetic-test-value'}
        self.assertIsNone(policy.make_web_tool(prohibited, env))
        self.assertEqual(policy.make_agent_tools('citation', 'python', prohibited, prohibited, env), ['citation'])

    def test_general_mode_requires_key_and_exposes_requested_tools(self):
        with self.assertRaises(ValueError):
            policy.make_web_tool(lambda **kw: kw, {'RAG_CORPUS_ONLY': 'false'})
        env = {'RAG_CORPUS_ONLY': 'false', 'TAVILY_API_KEY': 'synthetic-test-value'}
        tools = policy.make_agent_tools('citation', 'python', lambda: ['read_file'], lambda **kw: 'web', env)
        self.assertEqual(tools, ['python', 'web', 'citation', 'read_file'])
        with self.assertRaises(ValueError):
            policy.corpus_only_mode({'RAG_CORPUS_ONLY': 'typo'})

    def test_stop_rules_are_not_a_universal_point_nine_gate(self):
        rules = policy.evaluation_stop_reasons
        self.assertEqual(rules(.90, .2, 1, 5, ['gap']), ['completeness_at_least_0.90'])
        self.assertEqual(rules(.80, .78, 3, 5, ['gap']), ['limited_improvement'])
        self.assertEqual(rules(.40, .20, 5, 5, ['gap']), ['maximum_search_attempts'])
        self.assertEqual(rules(.50, .20, 2, 5, []), ['evaluator_no_missing_information'])
        self.assertEqual(rules(.75, .74, 3, 5, ['gap']), [])
        self.assertEqual(rules(.89, .4, 2, 5, ['gap']), [])


class CellOriginTests(unittest.TestCase):
    def grade(self, changes, counts=(10, 10), blockers=None, expression=(2., 1.)):
        cells = ['Hepatocytes', 'Myeloid cells']
        spec = SimpleNamespace(candidate_cell_types=cells, gene='Cirbp', tissue='Liver')
        expr = pd.DataFrame({'cell_type': cells, 'mean_expression': expression})
        contrast = pd.DataFrame({'cell_type': cells, 'mean_difference': changes,
                                 'n_young': [counts[0]] * 2, 'n_old': [counts[1]] * 2})
        return grading.grade_evidence(expr, contrast, spec, {'blockers': blockers or []}).iloc[0].verdict

    def test_archived_cirbp_summary_retains_its_descriptive_verdict(self):
        base = ROOT / 'analysis/cirbp_liver_single_cell/results'
        expression = pd.read_csv(base / 'cell_type_expression.tsv', sep='\t')
        contrast = pd.read_csv(base / 'young_old_contrast.tsv', sep='\t')
        spec = SimpleNamespace(candidate_cell_types=['Hepatocytes', 'Myeloid cells'], gene='Cirbp', tissue='Liver')
        result = grading.grade_evidence(expression, contrast, spec)
        self.assertEqual(result.iloc[0].verdict, 'hepatocyte-supported')

    def test_two_decreases_do_not_support_induction(self):
        self.assertEqual(self.grade((-.1, -.2)), 'weak')
        self.assertEqual(self.grade((0., 0.)), 'weak')
        self.assertEqual(self.grade((-.1, -.2), expression=(1., 2.)), 'weak')

    def test_positive_hepatocyte_contrast_retains_descriptive_label(self):
        self.assertEqual(self.grade((.2, -.1)), 'hepatocyte-supported')

    def test_absent_group_or_nonfinite_observation_is_insufficient(self):
        self.assertEqual(self.grade((.2, -.1), (0, 10)), 'insufficient')
        self.assertEqual(self.grade((float('nan'), .1)), 'insufficient')
        self.assertEqual(self.grade((.2, -.1), blockers=['young group not found']), 'insufficient')

    def test_mixed_expression_and_induction_are_not_assigned_to_immune_origin(self):
        self.assertEqual(self.grade((.2, -.1), expression=(1., 2.)), 'mixed')
        self.assertEqual(self.grade((.2, .2)), 'mixed')
        self.assertEqual(self.grade((-.1, .2), expression=(1., 2.)), 'immune-supported')


class ComparisonTests(unittest.TestCase):
    def test_sign_is_not_numerical_reproduction(self):
        self.assertEqual(comparison.match_label(1.001 - 1, 14.98 - 1, 'sign'), 'directionally-concordant')
        self.assertEqual(comparison.match_label(-.7, .1, 'sign'), 'directionally-discordant')

    def test_missing_or_nonfinite_values_cannot_match(self):
        for value in (None, float('nan'), float('inf')):
            self.assertEqual(comparison.match_label(value, 1., 'sign'), 'not-assessable')

    def test_significance_category_is_separate(self):
        self.assertEqual(comparison.match_label(.1881, .039, 'sig'), 'significance-category-disagreement')
        self.assertEqual(comparison.match_label(.1881, .5, 'sig'), 'significance-category-agreement')

    def test_equivalence_placeholder_does_not_become_an_agreement(self):
        row = comparison.comparison_entry('female_ASPC_Kdr_old_minus_young', .0013, None, 0., 'directionally-concordant')
        self.assertEqual(row['match'], 'not-assessable')
        self.assertIsNone(row['target'])
        self.assertEqual(row['legacy_target_placeholder'], 0.)


class GeneticsIntegrityTests(unittest.TestCase):
    def test_allele_swap_retains_frequency_audit_and_effect_sign(self):
        pqtl = {'effect_allele': 'G', 'other_allele': 'C', 'eaf': .0348, 'beta': -.8, 'se': .02}
        outcome = {'effect_allele': 'C', 'other_allele': 'G', 'eaf': .9653, 'beta': .0293, 'se': .009}
        result = genetics.harmonize(pqtl, outcome)
        self.assertEqual(result['beta_outcome'], -.0293)
        self.assertAlmostEqual(result['harmonized_outcome_eaf'], .0347)
        self.assertEqual(result['gwas_effect_allele'], 'C')
        self.assertTrue(result['palindromic'])
        self.assertEqual(result['alignment_review'], 'manual_frequency_review_required')

    def test_duplicate_position_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'outcome.tsv.gz'
            header = 'CHR\tPOS\tMARKER\tEFFECT_ALLELE\tOTHER_ALLELE\tEAF\tBETA\tSE\tPVAL\tN\n'
            row = '22\t50315382\trs74510325\tC\tG\t.9653\t.0293\t.009\t.001\t100\n'
            with gzip.open(path, 'wt') as handle:
                handle.write(header + row + row)
            with self.assertRaisesRegex(ValueError, 'Multiple outcome records'):
                genetics.read_outcome(path, '22', {50315382})

    def test_all_nineteen_archived_wald_estimates(self):
        path = ROOT / 'analysis/creld2_human_genetics/results/five_candidate_screen/original_outputs/hypothesis4_mr_lead_wald.tsv'
        with path.open() as handle:
            rows = list(csv.DictReader(handle, delimiter='\t'))
        self.assertEqual(len(rows), 19)
        for row in rows:
            with self.subTest(target=row['target'], outcome=row['outcome']):
                recomputed = genetics.wald(row)
                for key in ('mr_beta', 'mr_se', 'mr_p'):
                    self.assertTrue(math.isclose(recomputed[key], float(row[key]), rel_tol=1e-12, abs_tol=1e-15))

    def test_no_candidate_outcome_is_silently_omitted(self):
        path = ROOT / 'analysis/creld2_human_genetics/results/five_candidate_screen/all_candidate_outcomes.tsv'
        with path.open() as handle:
            rows = list(csv.DictReader(handle, delimiter='\t'))
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({(r['target'], r['outcome']) for r in rows}), 20)


if __name__ == '__main__':
    unittest.main()
