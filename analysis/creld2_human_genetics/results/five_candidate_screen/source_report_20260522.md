# Hypothesis 4 Verification: Metabolic Stress Adipokines and Adipose-Liver Axis

> 작성일: 2026-05-22
> 기준 경로: `<original local data root>`
> 대상 가설: `FGF21`, `CRELD2`, `GDF15`, `ADIPOQ-ADIPOR`, `SERPINE1` 기반 지방-순환-간 노화 축

## 1. 전체 판정

현재 로컬 데이터 기준으로 hypothesis4는 **부분 검증 가능**하다. 5개 target 모두 UKB-PPP pQTL이 있어 pQTL 기반 MR/coloc은 가능했다. 다만 엄격한 coloc 기준(PP.H4 > 0.8)을 만족한 target-outcome 조합은 없었다.

가장 눈에 띄는 결과는 `CRELD2 -> Frailty`이다. Lead pQTL Wald MR에서 nominal P=0.00117이고, pQTL x Frailty coloc PP.H4=0.526으로 원문에 적힌 완화 기준(PP4 > 0.5)은 넘는다. 그러나 PP.H4 > 0.8에는 미달하므로 강한 확정 근거가 아니라 **중등도 후보 신호**로 해석해야 한다.

| Target | 현재 판정 | 핵심 이유 |
|---|---|---|
| `FGF21` | pQTL 분석 가능, aging coloc 비지지 | pQTL은 강하지만 aging outcome PP.H4 낮음 |
| `CRELD2` | 가장 유망한 후보 | SAT/VAT/Liver eQTL 강함, Frailty PP.H4=0.526 |
| `GDF15` | 기존 결과와 동일하게 약함 | pQTL 강하나 adipose eQTL 약하고 aging PP.H4 낮음 |
| `ADIPOQ` | adipose-origin 강함, aging coloc 비지지 | SAT/VAT eQTL 매우 강함, pQTL 강함, aging PP.H4 낮음 |
| `SERPINE1` | pQTL 분석 가능, aging coloc 비지지 | parental longevity lead Wald nominal P=0.024이나 PP.H4 낮음 |

---

## 2. 데이터 가용성

### 2.1 UKB-PPP pQTL

| Target | pQTL availability | Local file |
|---|---:|---|
| `FGF21` | 있음 | `pQTL/ukbiobank/FGF21_Q9NSA1_OID21402_v1_Oncology.tar` |
| `CRELD2` | 있음 | `pQTL/ukbiobank/CRELD2_Q6UXH1_OID20751_v1_Inflammation.tar` |
| `GDF15` | 있음 | `pQTL/ukbiobank/GDF15_Q99988_OID20251_v1_Cardiometabolic.tar` |
| `ADIPOQ` | 있음 | `pQTL/ukbiobank/ADIPOQ_Q15848_OID30748_v1_Inflammation_II.tar` |
| `SERPINE1` | 있음 | `pQTL/ukbiobank/SERPINE1_P05121_OID20342_v1_Cardiometabolic.tar` |

### 2.2 GTEx v8 eQTL

| Target | SAT pval_beta | VAT pval_beta | Liver pval_beta | 해석 |
|---|---:|---:|---:|---|
| `FGF21` | row 없음 | row 없음 | 0.281 | adipose eQTL 근거 약함 |
| `CRELD2` | 1.86e-12 | 4.96e-22 | 3.53e-07 | adipose/liver eQTL 강함 |
| `GDF15` | 0.315 | 0.215 | 0.124 | adipose/liver eQTL 약함 |
| `ADIPOQ` | 8.16e-25 | 4.12e-16 | 0.903 | adipose-specific eQTL 매우 강함 |
| `SERPINE1` | 0.0855 | 0.393 | 0.0726 | nominal/약함 |

수용체 관련 eQTL은 `ADIPOR1`, `ADIPOR2`가 SAT/VAT/Liver에 row는 있으나 유의하지 않았고, `GFRAL`은 SAT eQTL만 확인되었다. 이는 receptor connectome을 직접 입증하기에는 부족하며, 별도 liver cell-type expression matrix가 필요하다.

---

## 3. pQTL Locus Manifest

| Target | Lead variant | Locus | Lead LOG10P | Locus variants |
|---|---|---:|---:|---:|
| `FGF21` | `19:49260677:A:C:imp:v1` | chr19:48,760,677-49,760,677 | 57.3305 | 6,679 |
| `CRELD2` | `22:50315382:C:G:imp:v1` | chr22:49,815,382-50,815,382 | 354.247 | 7,157 |
| `GDF15` | `19:18499858:T:C:imp:v1` | chr19:17,999,858-18,999,858 | 419.433 | 5,652 |
| `ADIPOQ` | `3:186551888:C:T:imp:v1` | chr3:186,051,888-187,051,888 | 198.67 | 6,453 |
| `SERPINE1` | `7:100776208:A:G:imp:v1` | chr7:100,276,208-101,276,208 | 36.2265 | 6,466 |

UKB-PPP pQTL 좌표는 `ID` 내부의 `chr:pos:ref:alt`를 우선 사용했다.

---

## 4. Lead pQTL Wald MR

이 결과는 LD-clumped IVW가 아니라 각 target의 lead pQTL 단일 variant Wald ratio이다. 방향성 탐색으로만 해석한다.

| Target | Outcome | MR beta | SE | P |
|---|---|---:|---:|---:|
| `FGF21` | Frailty | 0.0358 | 0.0278 | 0.197 |
| `FGF21` | GrimAge | 0.0277 | 0.319 | 0.931 |
| `FGF21` | Telomere | 0.000829 | 0.0168 | 0.961 |
| `FGF21` | Parental longevity | 0.0359 | 0.0189 | 0.0565 |
| `CRELD2` | Frailty | 0.0360 | 0.0111 | 0.00117 |
| `CRELD2` | GrimAge | 0.146 | 0.110 | 0.186 |
| `CRELD2` | Telomere | -0.00271 | 0.00685 | 0.692 |
| `CRELD2` | Parental longevity | 0.00428 | 0.00749 | 0.568 |
| `GDF15` | Frailty | 0.0166 | 0.0120 | 0.167 |
| `GDF15` | GrimAge | 0.145 | 0.115 | 0.208 |
| `GDF15` | Telomere | -0.0160 | 0.00728 | 0.0283 |
| `GDF15` | Parental longevity | 0.00334 | 0.00809 | 0.680 |
| `ADIPOQ` | Frailty | 0.00943 | 0.0166 | 0.570 |
| `ADIPOQ` | GrimAge | -0.158 | 0.151 | 0.298 |
| `ADIPOQ` | Telomere | -0.0140 | 0.0103 | 0.172 |
| `SERPINE1` | Frailty | -0.0522 | 0.0356 | 0.143 |
| `SERPINE1` | GrimAge | -0.480 | 0.332 | 0.149 |
| `SERPINE1` | Telomere | 0.0353 | 0.0211 | 0.0953 |
| `SERPINE1` | Parental longevity | 0.0545 | 0.0242 | 0.0240 |

`ADIPOQ x parental longevity`는 harmonized overlap이 없어 lead Wald MR을 산출하지 못했다.

---

## 5. pQTL x Aging GWAS Coloc

| Target | Outcome | SNPs | PP.H3 | PP.H4 | 판정 |
|---|---|---:|---:|---:|---|
| `FGF21` | Frailty | 3,054 | 0.0752 | 0.00481 | 비지지 |
| `FGF21` | GrimAge | 2,682 | 0.210 | 0.0195 | 비지지 |
| `FGF21` | Telomere | 5,643 | 0.0880 | 0.00125 | 비지지 |
| `FGF21` | Parental longevity | 4,722 | 0.971 | 0.000274 | 별도 신호 가능성 |
| `CRELD2` | Frailty | 3,595 | 0.0261 | 0.526 | 중등도 지지 |
| `CRELD2` | GrimAge | 3,204 | 0.156 | 0.0751 | 비지지 |
| `CRELD2` | Telomere | 6,125 | 0.721 | 0.00112 | 별도 신호 가능성 |
| `CRELD2` | Parental longevity | 5,237 | 0.0810 | 0.00437 | 비지지 |
| `GDF15` | Frailty | 2,748 | 0.139 | 0.00698 | 비지지 |
| `GDF15` | GrimAge | 2,570 | 0.218 | 0.0447 | 비지지 |
| `GDF15` | Telomere | 4,681 | 0.0883 | 0.0189 | 비지지 |
| `GDF15` | Parental longevity | 4,120 | 0.660 | 0.00078 | 별도 신호 가능성 |
| `ADIPOQ` | Frailty | 3,142 | 0.0360 | 0.00757 | 비지지 |
| `ADIPOQ` | GrimAge | 3,185 | 0.191 | 0.0594 | 비지지 |
| `ADIPOQ` | Telomere | 5,535 | 0.102 | 0.00920 | 비지지 |
| `ADIPOQ` | Parental longevity | 0 | NA | NA | overlap 부족 |
| `SERPINE1` | Frailty | 3,180 | 0.0270 | 0.00818 | 비지지 |
| `SERPINE1` | GrimAge | 3,291 | 0.224 | 0.0508 | 비지지 |
| `SERPINE1` | Telomere | 5,467 | 0.137 | 0.00595 | 비지지 |
| `SERPINE1` | Parental longevity | 4,729 | 0.0749 | 0.0239 | 비지지 |

엄격 기준 PP.H4 > 0.8을 만족하는 조합은 없다. 완화 기준 PP.H4 > 0.5를 적용하면 `CRELD2 x Frailty`만 통과한다.

---

## 6. Stage별 검증 가능성

| Stage | 원문 분석 | 현재 실행/판정 |
|---|---|---|
| Stage 1 | pQTL instrument selection, F-stat/R2 | Lead pQTL 및 locus 확인. F-stat/R2는 별도 산출 필요 |
| Stage 2 | Adipose TWAS/S-PrediXcan | 기존 TWAS/MAGMA 결과와 GTEx eQTL로 대체 평가. `CRELD2`, `ADIPOQ` adipose eQTL이 강함 |
| Stage 3 | IVW/Egger/Weighted median/MVMR | 이번에는 lead Wald MR만 수행. LD reference clumping 및 BMI GWAS 추가 후 확장 가능 |
| Stage 4 | coloc/SMR/HEIDI | pQTL x aging GWAS coloc 수행. `CRELD2 x Frailty`만 완화 기준 지지 |
| Stage 5 | Liver receptor annotation/connectome | GTEx Liver eQTL row 일부 확인. LIANA용 liver cell-type receptor matrix가 없어 직접 실행 불가 |

---

## 7. Target별 해석

### 7.1 FGF21

`FGF21`은 pQTL이 충분히 강하지만 adipose eQTL 근거가 약하고, aging outcome과의 PP.H4도 낮다. Parental longevity에서는 PP.H3=0.971로 pQTL과 outcome 양쪽에 별도 신호가 있을 가능성이 크지만, 같은 causal variant를 공유한다는 결론은 아니다.

### 7.2 CRELD2

`CRELD2`는 hypothesis4에서 가장 중요한 후보이다. SAT/VAT/Liver eQTL이 모두 강하고, pQTL도 매우 강하다. `CRELD2 -> Frailty`는 lead Wald MR P=0.00117, coloc PP.H4=0.526으로 완화 기준을 만족한다. 다만 PP.H4 > 0.8에는 미달하므로, 확정적이라기보다 우선 추적 대상이다.

### 7.3 GDF15

기존 hypothesis2/3 결과와 동일하다. pQTL은 매우 강하나 adipose eQTL이 약하고, aging outcome coloc은 낮다. `GDF15 -> telomere` nominal Wald 신호는 있지만 PP.H4가 낮아 causal variant 공유 근거는 약하다.

### 7.4 ADIPOQ-ADIPOR Axis

`ADIPOQ`는 SAT/VAT eQTL이 매우 강하고 pQTL도 강해 adipose-origin adipokine으로는 가장 생물학적으로 타당하다. 그러나 Frailty, GrimAge, Telomere와의 pQTL-GWAS coloc은 비지지이고, parental longevity는 overlap 부족으로 평가하지 못했다. `ADIPOR1/2` receptor 쪽은 GTEx eQTL 유의성이 낮아 receptor collapse를 통계유전학적으로 입증하지 못했다.

### 7.5 SERPINE1

`SERPINE1`은 pQTL이 있고 parental longevity lead Wald MR에서 nominal P=0.024를 보였지만, coloc PP.H4=0.0239로 낮다. 따라서 “senescence spreader가 전신 노화 지표를 직접 유도한다”는 주장에는 아직 약하다.

---

## 8. 최종 결론

hypothesis4는 이전 가설들보다 더 나은 후보를 하나 제공한다.

```text
CRELD2 strong adipose/liver eQTL
    -> strong circulating pQTL
    -> Frailty lead-Wald P=0.00117
    -> pQTL-Frailty coloc PP.H4=0.526
```

다만 엄격한 PP.H4 > 0.8 기준에서는 아직 확정적이지 않다. 현재 데이터 기준 우선순위는 다음과 같다.

1. `CRELD2 -> Frailty`: 후속 LD-clumped IVW/Egger 및 eQTL-pQTL coloc 최우선
2. `ADIPOQ`: adipose-origin은 강하지만 aging outcome 직접 근거는 약함
3. `FGF21`, `SERPINE1`, `GDF15`: pQTL-MR 가능하지만 현재 aging coloc 비지지

따라서 hypothesis4의 최종 판정은 다음이다.

> 현재 데이터는 `CRELD2-Frailty`를 중등도 후보 신호로 지지한다. 하지만 `FGF21`, `GDF15`, `ADIPOQ`, `SERPINE1`이 aging GWAS와 동일 causal variant를 공유한다는 근거는 부족하다. Liver connectome 및 MVMR까지 주장하려면 BMI GWAS, LD reference clumping, liver cell-type receptor annotation이 추가로 필요하다.

---

## 9. 산출물

| File | 내용 |
|---|---|
| `scripts/run_hypothesis4_pqtl_followup.py` | hypothesis4 pQTL-GWAS harmonization 및 lead Wald MR |
| `scripts/run_hypothesis4_coloc_r.R` | hypothesis4 R `coloc.abf` 실행 |
| `results/hypothesis4_followup/pqtl_locus_manifest.tsv` | pQTL lead locus manifest |
| `results/hypothesis4_followup/hypothesis4_mr_lead_wald.tsv` | lead pQTL Wald MR 결과 |
| `results/hypothesis4_followup/hypothesis4_coloc_abf_r.tsv` | pQTL x aging GWAS coloc 결과 |
| `results/hypothesis4_followup/*harmonized.tsv` | target-outcome별 harmonized variant set |
