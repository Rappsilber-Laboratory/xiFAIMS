# xiFAIMS

Module for analysis of crosslinking MS and FAIMS data.

# Modules
List of available modules:
- const - stores amino acids constants for feature computation
- explainer - stores code to use SHAP for explainable AI
- features - compute and manage feature computation
- ml - perform, document and store machine learning results
- plots - visual presentation of results
- processing - various pre and post processing tools


# performing the analysis

## running xirt
To run the various experiments with xiRT, navigate to the bash folder and simply run the
run_xirt.bat. This script will run a combination of parameters for xiRT (regression, ordinal) +-
auxilarry tasks. The results will be stored as tables (summaries) and plots (for each cv).
The resulting table must be analyzed in the notebook xirt_summary.ipynb