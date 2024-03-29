"""
SNAKEFILE to run the xifaims analysis as used in the manuscript.

Post-processing needs to be done.

example:

python xifaims_xgb.py --jobs 1 --xgb tiny --name 8PM4PM_CO_NAVG_tiny_nofeats --continuous --feature none -o results_2021  -c parameters/faims_all.yaml --infile data/combined_8PMLunique_4PMLS_nonu.csv

"""
GRID = "huge"

rule run_xifaims:
    input:
        "data/combined_8PMLunique_4PMLS_nonu.csv"
    params:
        name = "8PM4PM_CO_NAVG_" + GRID + "_nofeats",
        grid = GRID,
        features = "none",
        out = "results_2021",
        params = "parameters/faims_all.yaml"
    output:
        "results_2021/xifaims_8PM4PM_CO_NAVG_" + GRID + "_nofeats.p"
    shell:
        """python xifaims_xgb.py --jobs 1 --xgb {params.grid} --name {params.name} --continuous \
        --feature {params.features} -o {params.out}  -c {params.params} --infile {input}"""
