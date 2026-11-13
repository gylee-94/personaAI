"""Exercise runner path handling and failure behavior without atlas dependencies."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INPUTS = [
    "Fig3_Cirbp_Liver/raw.data/liver_hepatocyte_myeloid_full.h5ad",
    "Fig3_Cirbp_Liver/raw.data/Cirbp_categorized_with_clusters.h5ad",
    "Fig4_PGAT/raw.data/gWAT_male_30k.h5ad",
    "Fig4_PGAT/raw.data/gWAT_female_30k.h5ad",
]


class RevisionRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="revision runner ")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repository with spaces"
        self.cwd = self.base / "caller"
        self.repo.mkdir()
        self.cwd.mkdir()
        shutil.copy2(ROOT / "run_revision_analyses.sh", self.repo)
        self.record = self.base / "invocations.txt"
        interpreter = self.cwd / ".venv/bin/python"
        interpreter.parent.mkdir(parents=True)
        interpreter.write_text(
            '#!/usr/bin/env bash\n'
            'printf "%s|%s\\n" "$PWD" "$1" >> "$CALL_RECORD"\n'
            'printf "stub output\\n"\n'
            'if [[ -n "${FAIL_SCRIPT:-}" && "$1" == *"$FAIL_SCRIPT" ]]; then exit 7; fi\n'
        )
        interpreter.chmod(0o755)
        for name in INPUTS:
            p = self.cwd / "figure data" / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        (self.cwd / "atlas/gWAT_experiment").mkdir(parents=True)
        self.env = dict(os.environ, PYTHON=".venv/bin/python",
                        PERSONAAI_FIGURE_DATA="figure data", PERSONAAI_SOMA="atlas",
                        CALL_RECORD=str(self.record))
        self.env.pop("FAIL_SCRIPT", None)

    def run_runner(self):
        return subprocess.run(["bash", str(self.repo / "run_revision_analyses.sh")],
                              cwd=self.cwd, env=self.env, text=True, capture_output=True)

    def test_relative_interpreter_and_inputs_from_another_directory(self):
        result = self.run_runner()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.record.read_text().splitlines()
        self.assertEqual(len(calls), 8)
        self.assertTrue(all(Path(c.split("|", 1)[0]).resolve() == self.cwd.resolve() for c in calls))
        self.assertTrue(calls[0].endswith("01_cirbp_mouse_level.py"))
        self.assertTrue(calls[-1].endswith("05_vegfa_kdr_midlife.py"))
        self.assertEqual(len(list(self.repo.glob("analysis/*/revision/results/*.log"))), 8)

    def test_missing_input_stops_before_running_any_analysis(self):
        (self.cwd / "figure data" / INPUTS[-1]).unlink()
        result = self.run_runner()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gWAT_female_30k.h5ad", result.stderr)
        self.assertFalse(self.record.exists())

    def test_analysis_failure_stops_later_scripts(self):
        self.env["FAIL_SCRIPT"] = "02_c4_proportion_mouse_level.py"
        result = self.run_runner()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.record.read_text().splitlines()), 2)
        self.assertIn("02_c4_proportion_mouse_level.log", result.stderr)

    def test_missing_configuration_has_actionable_error(self):
        del self.env["PERSONAAI_SOMA"]
        result = self.run_runner()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PERSONAAI_SOMA", result.stderr)
        self.assertFalse(self.record.exists())


if __name__ == "__main__":
    unittest.main()
