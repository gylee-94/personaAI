#!/usr/bin/env bash
# Run the author-supplied primary revision statistics for Figures 3 and 4.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python}"
: "${PERSONAAI_FIGURE_DATA:?set PERSONAAI_FIGURE_DATA (see docs/revision_analyses.md)}"
: "${PERSONAAI_SOMA:?set PERSONAAI_SOMA (see docs/revision_analyses.md)}"

# Keep the caller's working directory: relative interpreter and input paths
# must still resolve after moving between the CIRBP and PGAT analyses.
if ! command -v "$PY" >/dev/null 2>&1; then
    printf 'Python interpreter not executable: %s\n' "$PY" >&2
    exit 1
fi
for rel in \
    Fig3_Cirbp_Liver/raw.data/liver_hepatocyte_myeloid_full.h5ad \
    Fig3_Cirbp_Liver/raw.data/Cirbp_categorized_with_clusters.h5ad \
    Fig4_PGAT/raw.data/gWAT_male_30k.h5ad \
    Fig4_PGAT/raw.data/gWAT_female_30k.h5ad; do
    if [[ ! -f "$PERSONAAI_FIGURE_DATA/$rel" ]]; then
        printf 'Missing figure source object: %s\n' "$PERSONAAI_FIGURE_DATA/$rel" >&2
        exit 1
    fi
done
if [[ ! -d "$PERSONAAI_SOMA/gWAT_experiment" ]]; then
    printf 'Missing atlas store: %s\n' "$PERSONAAI_SOMA/gWAT_experiment" >&2
    exit 1
fi

run_case() {
    local case_name="$1"
    shift
    local base="$ROOT/analysis/$case_name/revision"
    local script log
    mkdir -p "$base/results"
    for script in "$@"; do
        log="$base/results/$script.log"
        printf 'Running %s/%s\n' "$case_name" "$script"
        if ! "$PY" "$base/scripts/$script.py" > "$log" 2>&1; then
            printf 'Analysis failed; see %s\n' "$log" >&2
            return 1
        fi
    done
}

run_case cirbp_liver_single_cell \
    01_cirbp_mouse_level 02_c4_proportion_mouse_level 03_c4_senescence_gene_sets
run_case pgat_aspc_single_cell \
    01_extract_gwat_from_atlas 02_vec_proportion_mouse_level \
    03_vec_proportion_quasibinomial 04_midlife_contrasts 05_vegfa_kdr_midlife
printf 'Done; logs are in analysis/*/revision/results/.\n'
