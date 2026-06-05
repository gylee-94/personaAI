from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd


HYPOTHESIS_TEXT = """
테마 2: 간(Liver) - CIRBP 발현 증가의 이중적 기원 탐색

가설 A (간세포 스트레스 가설): 단일세포 분석에서 간세포 클러스터에서
연령에 따른 CIRBP 발현 증가가 뚜렷하게 나타날 것이다.

가설 B (면역세포 활성화 가설): 쿠퍼 세포 또는 기타 간 면역세포
클러스터에서 CIRBP 발현이 노년층에서 현저히 높게 나타날 것이다.
"""


def _write_liver_fixture(path: Path):
    obs = pd.DataFrame(
        {
            "Genotype": ["WT"] * 16,
            "Sex": [
                "Male", "Male", "Female", "Female",
                "Male", "Male", "Female", "Female",
                "Male", "Male", "Female", "Female",
                "Male", "Male", "Female", "Female",
            ],
            "Age_group": [
                "03_months", "23_months", "03_months", "23_months",
                "03_months", "23_months", "03_months", "23_months",
                "03_months", "23_months", "03_months", "23_months",
                "03_months", "23_months", "03_months", "23_months",
            ],
            "Main_cell_type": [
                "Hepatocytes", "Hepatocytes", "Hepatocytes", "Hepatocytes",
                "Hepatocytes", "Hepatocytes", "Hepatocytes", "Hepatocytes",
                "Myeloid cells", "Myeloid cells", "Myeloid cells", "Myeloid cells",
                "Myeloid cells", "Myeloid cells", "Myeloid cells", "Myeloid cells",
            ],
        },
        index=[f"cell{i}" for i in range(16)],
    )
    x = np.array(
        [
            [1.0], [8.0], [1.0], [7.0],
            [2.0], [9.0], [2.0], [8.0],
            [1.0], [2.0], [1.0], [2.0],
            [0.0], [1.0], [0.0], [1.0],
        ]
    )
    ad.AnnData(X=x, obs=obs, var=pd.DataFrame(index=["Cirbp"])).write_h5ad(path)


def _write_hepatocyte_only_fixture(path: Path):
    obs = pd.DataFrame(
        {
            "Genotype": ["WT"] * 4,
            "Sex": ["Male", "Male", "Female", "Female"],
            "Age_group": ["03_months", "23_months", "03_months", "23_months"],
            "Main_cell_type": ["Hepatocytes"] * 4,
        },
        index=[f"hep{i}" for i in range(4)],
    )
    ad.AnnData(
        X=np.array([[1.0], [4.0], [1.0], [5.0]]),
        obs=obs,
        var=pd.DataFrame(index=["Cirbp"]),
    ).write_h5ad(path)


def test_parse_inline_hypothesis_extracts_scrna_spec():
    from sc_analysis_mcp.scrna_report_runner import parse_inline_hypothesis

    spec = parse_inline_hypothesis(HYPOTHESIS_TEXT)

    assert spec.hypothesis_id == "scrna_liver_cirbp_origin"
    assert spec.tissue == "Liver"
    assert spec.gene == "Cirbp"
    assert spec.candidate_cell_types == ["Hepatocytes", "Myeloid cells"]
    assert spec.young_groups == ["03_months"]
    assert spec.old_groups == ["23_months"]


def test_run_scrna_report_writes_report_tables_and_figures(tmp_path: Path):
    from sc_analysis_mcp.scrna_report_runner import parse_inline_hypothesis, run_report

    h5ad_path = tmp_path / "liver_fixture.h5ad"
    _write_liver_fixture(h5ad_path)
    spec = parse_inline_hypothesis(HYPOTHESIS_TEXT)
    output_dir = tmp_path / "report"

    result = run_report(spec, HYPOTHESIS_TEXT, h5ad_path, output_dir)

    assert result.report_path == output_dir / "report.md"
    assert result.report_path.exists()
    assert (output_dir / "spec.json").exists()
    assert (output_dir / "feasibility.json").exists()
    assert (output_dir / "results" / "cell_type_expression.tsv").exists()
    assert (output_dir / "results" / "age_trajectory.tsv").exists()
    assert (output_dir / "results" / "young_old_contrast.tsv").exists()
    assert (output_dir / "results" / "evidence_grading.tsv").exists()
    assert (output_dir / "figures" / "F1_cell_type_expression.png").exists()
    assert (output_dir / "figures" / "F2_age_trajectory_by_sex.png").exists()
    assert (output_dir / "figures" / "F3_young_old_contrast.png").exists()
    assert (output_dir / "figure_manifest.tsv").exists()

    report = result.report_path.read_text()
    assert "Hypothesis A" in report
    assert "Hepatocytes" in report
    assert "Myeloid cells" in report
    assert "hepatocyte-supported" in report


def test_preflight_resolves_gene_case_and_cell_type_alias(tmp_path: Path):
    from sc_analysis_mcp.scrna_report_runner import (
        ScrnaHypothesisSpec,
        preflight_aging_atlas,
    )

    h5ad_path = tmp_path / "liver_fixture.h5ad"
    _write_liver_fixture(h5ad_path)
    spec = ScrnaHypothesisSpec(
        hypothesis_id="scrna_liver_cirbp_origin",
        tissue="Liver",
        gene="CIRBP",
        candidate_cell_types=["hepatocyte", "Kupffer cells"],
        young_groups=["03_months"],
        old_groups=["23_months"],
    )

    check = preflight_aging_atlas(h5ad_path, spec)

    assert check["feasible"] is True
    assert check["gene_resolution"]["resolved_gene"] == "Cirbp"
    assert check["gene_resolution"]["match_kind"] == "varname_case"
    assert check["cell_type_resolution"]["hepatocyte"]["matched_value"] == "Hepatocytes"
    assert check["cell_type_resolution"]["Kupffer cells"]["matched_value"] == "Myeloid cells"
    assert check["blockers"] == []


def test_dataset_resolver_prefers_lineage_file_with_all_candidate_cells(tmp_path: Path):
    from sc_analysis_mcp.scrna_report_runner import (
        parse_inline_hypothesis,
        resolve_dataset_for_spec,
    )

    hepatocyte_only = tmp_path / "aging_atlas_clustered.h5ad"
    lineage = tmp_path / "liver_hepatocyte_myeloid_comparison.h5ad"
    _write_hepatocyte_only_fixture(hepatocyte_only)
    _write_liver_fixture(lineage)

    spec = parse_inline_hypothesis(HYPOTHESIS_TEXT)
    selection = resolve_dataset_for_spec(
        spec,
        candidates=[hepatocyte_only, lineage],
        intent="lineage_screening",
    )

    assert selection["selected_path"] == lineage
    assert selection["selected_preflight"]["feasible"] is True
    assert selection["candidate_scores"][0]["path"] == str(lineage)
    assert selection["candidate_scores"][1]["blocker_count"] > 0
