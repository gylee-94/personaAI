"""Figure 3D-G: independently defined senescence gene sets, C4 versus other hepatocytes.

Sets (MSigDB, fetched 2026-10-13):
  FRIDMAN_SENESCENCE_UP (Fridman & Tainsky, Oncogene 2008; human symbols mapped to mouse by case, TP53 -> Trp53)
  GOBP_CELLULAR_SENESCENCE (mouse)
Scoring: scanpy.tl.score_genes (ctrl_size 50, 25 bins, random_state 0) on the log-normalized X.
Test: C4 versus all other hepatocytes (cells, two-sided Mann-Whitney).

Manuscript: Results, Figure 3D-G paragraph. Response letter R1.5 (3), R2.4, R3.4.
"""
import anndata as ad
import scanpy as sc
from scipy import stats

from _paths import fig3dg_object

FRIDMAN_HS = """OPTN CDKN1A CDKN1C CDKN2A CDKN2B CDKN2D CITED2 HTATIP2 HBS1L RAB31 ESM1 HPS5 FILIP1L CLTB COL1A2 CRYAB CCN2
CYP1B1 F3 ALDH1A3 FN1 TES GSN GUK1 NRG1 HSPA2 IGSF3 IFI16 IFNG IGFBP1 IGFBP2 IGFBP3 IGFBP4 IGFBP5 IGFBP6 IGFBP7 ING1 IRF5
IRF7 RHOB MDM2 MMP1 NDN NME2 SERPINE1 SERPINB2 MAP2K3 RGL2 RAB5B RAB13 RABGGTA RAC1 RBL2 CCND1 RRAS S100A11 SMURF2 SMPD1
SOD1 SPARC STAT1 TFAP2A TGFB1I1 THBS1 TNFAIP2 TNFAIP3 TP53 VIM MAP1LC3B AOPEP TSPYL5 PEA15 CREG1 EIF2S2 CXCL14 CD44
ISG15""".split()
FRIDMAN = [g.capitalize().replace("Tp53", "Trp53") for g in FRIDMAN_HS]
GOBP = """Fbxo4 Abl1 Pawr Prelp Ang Arg2 Bmal1 B2m Bcl6 Bmpr1a Brca2 Calr Cav1 Cdk6 Cdkn1a Cdkn2a Cdkn2b Comp Gch1 Htt Hmga1
Hmga2 Hras Id2 Ilk Kras Lmna Mapkapk5 Mif Mnt Npm1 Nup62 Prkcd Pla2r1 Pml Prkdc Pten Rbl1 Spi1 Plk2 Srf Suv39h1 Tbx2 Tbx3
Cgas Terf2 Tert Top2b Trp53 Twist1 Wnt1 Wrn Smc5 Ybx1 Zfp217 Zmpste24 Akt3 Vash1 Nek4 Kat6a Map2k1 Mapk14 Zmiz1 Morc3
Ndufs6 Sirt6 Fzr1 Mtor Icmt Nampt Ypel3 Eef1e1 Rsl1d1 Abi3 Fbxo5 Smc6 Nsmce2 Pnpt1 Zkscan3 Pot1b Opa1 Bcl2l12 Nuak1 Gins3
Ecrg4 Dnaja3 Wnt16 Sirt1 Prmt6""".split()

a = ad.read_h5ad(fig3dg_object())
c4 = a.obs.cluster.astype(str) == "C3"   # h5ad 'C3' = figure C4
for name, gl in [("Fridman senescence-up", FRIDMAN), ("GO:BP cellular senescence", GOBP)]:
    genes = [g for g in dict.fromkeys(gl) if g in a.var_names]
    sc.tl.score_genes(a, genes, ctrl_size=50, n_bins=25, use_raw=False, random_state=0, score_name="s")
    p = stats.mannwhitneyu(a.obs.s[c4], a.obs.s[~c4]).pvalue
    print(f"{name}: C4 vs other hepatocytes, Mann-Whitney P = {p:.1g}")
