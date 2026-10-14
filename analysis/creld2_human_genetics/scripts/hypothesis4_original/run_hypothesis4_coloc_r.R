#!/usr/bin/env Rscript

.libPaths(c("<original local R library>", .libPaths()))

suppressPackageStartupMessages({
  library(data.table)
  library(coloc)
})

root <- "<original local data root>"
out_dir <- file.path(root, "results", "hypothesis4_followup")
targets <- c("fgf21", "creld2", "gdf15", "adipoq", "serpine1")
outcomes <- c("frailty", "grimage", "telomere", "parental_longevity")

run_one <- function(target, outcome) {
  path <- file.path(out_dir, sprintf("%s_%s.harmonized.tsv", target, outcome))
  dt <- fread(path)
  dt <- dt[
    is.finite(beta_exposure) &
      is.finite(se_exposure) &
      is.finite(beta_outcome) &
      is.finite(se_outcome) &
      is.finite(pqtl_eaf) &
      pqtl_eaf > 0 &
      pqtl_eaf < 1
  ]
  if (nrow(dt) < 50) {
    return(data.table(
      target = toupper(target),
      outcome = outcome,
      status = "insufficient_overlap",
      nsnps = nrow(dt),
      PP.H0 = NA_real_,
      PP.H1 = NA_real_,
      PP.H2 = NA_real_,
      PP.H3 = NA_real_,
      PP.H4 = NA_real_
    ))
  }
  d1 <- list(
    beta = dt$beta_exposure,
    varbeta = dt$se_exposure^2,
    snp = dt$pqtl_variant_id,
    MAF = pmin(dt$pqtl_eaf, 1 - dt$pqtl_eaf),
    N = as.integer(median(dt$pqtl_n, na.rm = TRUE)),
    type = "quant",
    sdY = 1
  )
  d2 <- list(
    beta = dt$beta_outcome,
    varbeta = dt$se_outcome^2,
    snp = dt$pqtl_variant_id,
    MAF = pmin(dt$pqtl_eaf, 1 - dt$pqtl_eaf),
    N = as.integer(median(dt$gwas_n, na.rm = TRUE)),
    type = "quant",
    sdY = 1
  )
  res <- coloc.abf(dataset1 = d1, dataset2 = d2)
  pp <- as.list(res$summary)
  data.table(
    target = toupper(target),
    outcome = outcome,
    status = "ok",
    nsnps = as.integer(pp[["nsnps"]]),
    PP.H0 = as.numeric(pp[["PP.H0.abf"]]),
    PP.H1 = as.numeric(pp[["PP.H1.abf"]]),
    PP.H2 = as.numeric(pp[["PP.H2.abf"]]),
    PP.H3 = as.numeric(pp[["PP.H3.abf"]]),
    PP.H4 = as.numeric(pp[["PP.H4.abf"]])
  )
}

results <- rbindlist(lapply(targets, function(target) {
  rbindlist(lapply(outcomes, function(outcome) run_one(target, outcome)), fill = TRUE)
}), fill = TRUE)
fwrite(results, file.path(out_dir, "hypothesis4_coloc_abf_r.tsv"), sep = "\t")
print(results)
