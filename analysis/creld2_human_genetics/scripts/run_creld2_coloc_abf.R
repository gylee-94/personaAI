#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(data.table)
  library(coloc)
})

args <- commandArgs(trailingOnly = TRUE)
out_dir <- NULL
for (i in seq_along(args)) {
  if (args[[i]] == "--out" && i < length(args)) {
    out_dir <- args[[i + 1]]
  }
}
if (is.null(out_dir)) {
  stop("Usage: Rscript run_creld2_coloc_abf.R --out <directory>")
}

outcomes <- c("frailty", "telomere", "parental_longevity")

is_palindromic <- function(a1, a2) {
  pair <- paste0(a1, a2)
  pair %in% c("AT", "TA", "CG", "GC")
}

run_one <- function(outcome, drop_palindromic = FALSE) {
  path <- file.path(out_dir, sprintf("creld2_%s.harmonized.tsv", outcome))
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
  if (drop_palindromic) {
    dt <- dt[!is_palindromic(pqtl_effect_allele, pqtl_other_allele)]
  }
  if (nrow(dt) < 50) {
    return(data.table(
      target = "CRELD2",
      outcome = outcome,
      analysis = ifelse(drop_palindromic, "exclude_palindromic", "primary"),
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
    target = "CRELD2",
    outcome = outcome,
    analysis = ifelse(drop_palindromic, "exclude_palindromic", "primary"),
    status = "ok",
    nsnps = as.integer(pp[["nsnps"]]),
    PP.H0 = as.numeric(pp[["PP.H0.abf"]]),
    PP.H1 = as.numeric(pp[["PP.H1.abf"]]),
    PP.H2 = as.numeric(pp[["PP.H2.abf"]]),
    PP.H3 = as.numeric(pp[["PP.H3.abf"]]),
    PP.H4 = as.numeric(pp[["PP.H4.abf"]])
  )
}

results <- rbindlist(c(
  lapply(outcomes, run_one, drop_palindromic = FALSE),
  list(run_one("frailty", drop_palindromic = TRUE))
), fill = TRUE)

fwrite(results, file.path(out_dir, "creld2_coloc_abf.tsv"), sep = "\t")
print(results)
