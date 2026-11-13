"""Extract gWAT (perigonadal adipose tissue) cell metadata from the Mouse Aging Atlas SOMA store.

Writes intermediate/gWAT_obs.parquet (read by 02 and 04) and prints the wild-type cells by sex and the wild-type
mice per sex and age.

Manuscript: Methods, Sampling ("Figure 4D is calculated from all wild-type cells of each mouse (364,044 cells in males
and 336,080 in females; 16 mice per sex)"); Figure 4 legend (mice per sex and age).
"""
import tiledbsoma as soma

from _common import INTER, load_obs, soma_base

COLS = ["soma_joinid", "Genotype", "Sex", "Age_group", "Main_cell_type", "ID", "UMI_count", "Gene_count", "cell_barcode"]

with soma.open(str(soma_base() / "gWAT_experiment")) as exp:
    exp.obs.read(column_names=COLS).concat().to_pandas().to_parquet(INTER / "gWAT_obs.parquet")
wt = load_obs("gWAT").query("Genotype == 'WT'")
print("Wild-type cells by sex:", wt.Sex.astype(str).value_counts().to_dict())
print("Wild-type mice per sex and age:")
print(wt.groupby(["Sex", "Age_group"], observed=True).ID.nunique().unstack().to_string())
