# -*- coding: utf-8 -*-
"""
Created on Wed Oct 14 21:56:23 2020

@author: hanjo
"""
import os
import pandas as pd
import yaml
import sys

from xifaims import processing as xp
from xifaims import features as xf
from xifaims import plots as xpl
from xifaims import ml as xml
from sklearn.metrics import mean_squared_error
from scipy.stats import pearsonr

# setup
# scale = True
# nonunique = True
# charge = "all"
# prefix = "all_features"
# exclude = []
# include = []

#config_loc = sys.argv[1]
#infile_loc = sys.argv[2]


def summarize_df(all_clf):
    # summarize data in dataframe
    res_df = {"clf": [], "set": [], "pearson": [], "r2": [], "mse": []}
    for ii, grpi in all_clf.groupby(["classifier", "Set"]):
        res_df["clf"].append(ii[0])
        res_df["set"].append(ii[1])
        res_df["pearson"].append(pearsonr(grpi["CV_Train"], grpi["CV_Predict"])[0])
        res_df["r2"].append(pearsonr(grpi["CV_Train"], grpi["CV_Predict"])[0]**2)
        res_df["mse"].append(mean_squared_error(grpi["CV_Train"], grpi["CV_Predict"]))
    
    res_df = pd.DataFrame(res_df)
    res_df = res_df.round(2)
    res_df["run"] = prefix
    res_df = res_df.sort_values(by=["clf", "set", "pearson"])
    return res_df
#%%
# parsing and options
infile_loc = "data/4PM_DSS_LS_nonunique1pCSM.csv"
config_loc = "parameters/faims_all.yaml"
prefix = os.path.basename(config_loc.split(".")[0]) + "-" + os.path.basename(infile_loc.replace(".csv", ""))
config = yaml.load(open(config_loc), Loader=yaml.FullLoader)
print(config)
dir_res = os.path.join("results", prefix)
if not os.path.exists(dir_res):
    os.makedirs(dir_res)
############################################################

# read file and annotate CV
df = pd.read_csv(infile_loc)

# set cv
df["CV"] = - df["run"].apply(xp.get_faims_cv)

# remove non-unique
df = xp.preprocess_nonunique(df)
# split into targets and decoys
df_TT, df_DX = xp.split_target_decoys(df)

# filter by charge
df_TT = xp.charge_filter(df_TT, config["charge"])
df_DX = xp.charge_filter(df_DX, config["charge"])

# compute features
df_TT_features = xf.compute_features(df_TT)
df_DX_features = xf.compute_features(df_DX)
# drop_features = ["proline", "DE", "KR", "log10mass", "Glycine"]
df_TT_features = df_TT_features.drop(config["exclude"], axis=1)
df_DX_features = df_DX_features.drop(config["exclude"], axis=1)

xpl.feature_correlation_plot(df_TT_features, dir_res, prefix="TT_")
#%%
# train baseline
# classifier
print("SVM ...")
svm_options = {"jobs": 8, "type": "SVC"}
svm_predictions, svm_metric, svm_gs, svm_clf = xml.training(df_TT, df_TT_features, model="SVM",
                                                            scale=True, model_args=svm_options)

# regression
print("SVR ...")
svm_options = {"jobs": 8, "type": "SVR"}
svr_predictions, svr_metric, svr_gs, svr_clf = xml.training(df_TT, df_TT_features, model="SVM",
                                                            scale=True, model_args=svm_options)

# classification
print("XGB ...")
xgb_options = {"grid": "tiny", "jobs": 1}
xgb_predictions, xgb_metric, xgb_gs, xgb_clf = xml.training(df_TT, df_TT_features, model="XGB",
                                                            scale=True, model_args=xgb_options)

# classification
print("FNN ...")
FNN_options = {"grid": "tiny"}
FNN_predictions, fnn_metric, fnn_gs, fnn_clf = xml.training(df_TT, df_TT_features, model="FNN",
                                                            scale=True, model_args=FNN_options)

# %% organize results
# concat to one dataframe for easier plotting
all_clf = pd.concat([svm_predictions, xgb_predictions, FNN_predictions])
all_clf["run"] = prefix
all_clf["config"] = config_loc
all_clf["infile"] = infile_loc
all_clf["run"] = prefix

all_metrics = pd.concat([svm_metric, xgb_metric, fnn_metric])
all_metrics["config"] = config_loc
all_metrics["infile"] = infile_loc
all_metrics["run"] = prefix

# summarize data
res_df = summarize_df(all_clf)
# %% store data
all_clf.to_csv(os.path.join(dir_res, "{}_summary_CV.csv".format(prefix)))
all_metrics.to_csv(os.path.join(dir_res, "{}_all_metrics.csv".format(prefix)))
res_df.to_csv(os.path.join(dir_res, "{}_summary_predictions.csv".format(prefix)))
print("Done.")

# print ("QC Plots")
# xpl.train_test_scatter_plot(all_clf, dir_res)
# xpl.cv_performance_plot(all_metrics, dir_res)