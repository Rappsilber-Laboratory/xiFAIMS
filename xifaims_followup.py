# -*- coding: utf-8 -*-
"""
Created on Wed Oct 14 21:56:23 2020

@author: hanjo
"""
import os

import numpy as np
import pandas as pd
import xgboost
import yaml
# from mlxtend.classifier import StackingClassifier
from mlxtend.feature_selection import SequentialFeatureSelector
from mlxtend.plotting import plot_sequential_feature_selection as plot_sfs
from scipy.stats import pearsonr
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from xifaims import features as xf
from xifaims import ml as xml
from xifaims import plots
from xifaims import processing as xp
from xifaims import parameters as xs

import seaborn as sns
import matplotlib.pyplot as plt


def feature_selection_xgb(df_TT_features, df_TT):
    """
    Perform Feature selection using SequentialFeatureSelector
    """
    # regressor
    xgbr_gs.best_params_["nthread"] = 8
    xgbr = xgboost.XGBRegressor(**xgbr_gs.best_params_)
    # feature selection
    sfs = SequentialFeatureSelector(xgbr, k_features="parsimonious", forward=True, floating=False,
                                    verbose=2, scoring="neg_mean_squared_error", cv=3)
    sfs = sfs.fit(df_TT_features, df_TT["CV"])
    # result summary
    df_res_sfs = pd.DataFrame.from_dict(sfs.get_metric_dict()).T
    selected_features = sfs.k_feature_idx_

    # vizualization
    f, ax = plot_sfs(sfs.get_metric_dict(), kind='std_dev')
    sns.despine(ax=ax)
    plt.show()

    print('best combination (Regression: %.3f): %s\n' % (sfs.k_score_, sfs.k_feature_idx_))
    print('all subsets:\n', sfs.subsets_)
    return df_res_sfs, sfs, df_TT_features.columns[list(selected_features)]

def get_cv_predictions(X, y, Xdx, ydx, xgbr_gs):
    """
    Use the best parameter model to perform predictions within the CV-folds.

    This function will loop over Stratified folds and then predict the CV based on the training
    set for the test set. Therefore, each CV-fold will get its own training instance.

    X = df_TT_features
    y = df_TT["CV"]
    Xdx = df_DX_features
    ydx = df_DX["CV"
    """
    # set up CV, stratify on CVs
    skf = StratifiedKFold(n_splits=3)
    skf.get_n_splits(X, y)

    # init datastructures
    pearson = []
    names = np.tile(["Train", "Predict"], 3)
    predictions_df = pd.DataFrame(index=X.index)
    predictions_df["Predicted CV"] = 100
    predictions_df["CV-FOLD"] = -1
    predictions_df["Observed CV"] = 100
    clfs_cv = []
    for cc, (train_index, test_index) in enumerate(skf.split(X, y), start=1):
        print("TRAIN:", train_index, "TEST:", test_index)
        # get train and test splits
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]

        # fit regressor
        xgb_clf = xgboost.XGBRegressor(**xgbr_gs.best_params_).fit(X_train, y_train)
        clfs_cv.append(xgb_clf)

        # predict
        xtrain_hat = xgb_clf.predict(X_train)
        xtest_hat = xgb_clf.predict(X_test)

        # some metrics
        pearson.append(pearsonr(xtrain_hat, y_train)[0])
        pearson.append(pearsonr(xtest_hat, y_test)[0])

        # store predictions in df
        predictions_df["Predicted CV"].iloc[test_index] = xtest_hat
        predictions_df["Observed CV"].iloc[test_index] = y_test
        predictions_df["CV-FOLD"].iloc[test_index] = cc
        predictions_df["Type"] = "TT"

    # store summary settings
    res_df = pd.DataFrame(pearson).transpose()
    res_df.columns = names
    res_df = res_df.transpose().reset_index().round(2)
    res_df.columns = ["setting", "pearsonr"]
    print(res_df)
    best_idx = res_df[res_df["setting"] == "Predict"].reset_index().sort_values(by="pearsonr", ascending=False).index[0]

    # predict decoy data
    predictions_df_decoys = pd.DataFrame(clfs_cv[best_idx].predict(Xdx))
    predictions_df_decoys.columns = ["Predicted CV"]
    predictions_df_decoys["Observed CV"] = ydx
    predictions_df_decoys["CV-FOLD"] = -1

    # store right decoy annotation
    predictions_df_decoys["Type"] = df_DX[["isTD", "isDD"]].idxmax(axis=1).str.replace("is", "")
    CV_predictions = pd.concat([predictions_df, predictions_df_decoys])
    # g = sns.jointplot(x="Observed CV", y="Predicted CV", data=concat_df, hue="Type")
    # g.ax_joint._axes.plot([-80, -10], [-80, -10], c="k", lw="2", alpha=0.7, ls="--")
    # plt.show()
    return CV_predictions

def single_peptide_predictions():
    """
    Function to use the trained classifier to predict the CV only based on features
    of a single peptide by either stting pepseq1 or pepseq2 to "". Note that some features
    such as m/z remained unchanged since they are taken from the CSM file.
    """
    df_TT_p1, df_TT_p2 = df_TT.copy(), df_TT.copy()
    df_TT_p1["PepSeq2"] = ""
    df_TT_p2["PepSeq1"] = ""
    df_TT_p1_features = xf.compute_features(df_TT_p1, onehot=one_hot).drop(config["exclude"],
                                                                           axis=1)
    df_TT_p2_features = xf.compute_features(df_TT_p2, onehot=one_hot).drop(config["exclude"],
                                                                           axis=1)
    df_DX_p1, df_DX_p2 = df_DX.copy(), df_DX.copy()
    df_DX_p1["PepSeq2"] = ""
    df_DX_p2["PepSeq1"] = ""
    df_DX_p1_features = xf.compute_features(df_DX_p1, onehot=one_hot).drop(config["exclude"],
                                                                           axis=1)
    df_DX_p2_features = xf.compute_features(df_DX_p2, onehot=one_hot).drop(config["exclude"],
                                                                           axis=1)
    TT_p1 = xgbr_clf.predict(df_TT_p1_features[df_TT_features.columns])
    TT_p2 = xgbr_clf.predict(df_TT_p2_features[df_TT_features.columns])
    DX_p1 = xgbr_clf.predict(df_DX_p1_features[df_TT_features.columns])
    DX_p2 = xgbr_clf.predict(df_DX_p2_features[df_TT_features.columns])
    single_peps = pd.DataFrame(np.concatenate([TT_p1, TT_p2, DX_p1, DX_p2]))
    single_peps["Type"] = np.repeat(["P1-TT", "P2-TT", "P1-DX", "P2-DX"], (len(TT_p1), len(TT_p1),
                                                                           len(DX_p1), len(DX_p1),))
    sns.boxplot(y=0, x="Type", data=single_peps)
    plt.show()

############################################################

def feature_selection():
    """
    Perform feature selection on single parameter.
    """
    xgbr_gs.best_params_["nthread"] = 8
    xgbr = xgboost.XGBRegressor(**xgbr_gs.best_params_)

    # feature selection
    sfs = SequentialFeatureSelector(xgbr, k_features="parsimonious", forward=True, floating=False,
                                    verbose=2, scoring="neg_mean_squared_error", cv=3)
    sfs = sfs.fit(df_TT_features, df_TT["CV"])
    # result summary
    df_res_sfs = pd.DataFrame.from_dict(sfs.get_metric_dict()).T
    selected_features = sfs.k_feature_idx_
    return df_res_sfs, selected_features

#%%
# # parsing and options
results_dir = "results_dev"
infile_loc = "data/combined_8PMLunique_4PMLS_nonu.csv"
infile_loc = "data/293T_DSSO_nonunique1pCSM.csv"
infile_val_loc = "data/26S_BS3_LS_nonunique1pCSM.csv"
config_loc = "parameters/faims_structure_selection.yaml"
config_loc = "parameters/faims_all.yaml"
one_hot = False

# %%
prefix = os.path.basename(config_loc.split(".")[0]) + "-" + os.path.basename(infile_loc.replace(".csv", ""))
config = yaml.load(open(config_loc), Loader=yaml.FullLoader)
config["grid"] = "small"
config["jobs"] = -1
print(config)
dir_res = os.path.join(results_dir, prefix)
if not os.path.exists(dir_res):
    os.makedirs(dir_res)

# input data
df_TT, df_DX = xp.process_csms(infile_loc)
df_TT_features, df_DX_features = xp.process_features(df_TT, df_DX, one_hot, config)

# regression
print("Hyperparameter Optimization ...")
xgb_options = {"grid": config["grid"], "jobs": config["jobs"], "type": "XGBR"}
xgbr_predictions, xgbr_metric, xgbr_gs, xgbr_clf = xml.training(df_TT, df_TT_features, model="XGB",
                                                                scale=True, model_args=xgb_options)

# store shap data
xp.store_for_shap(df_TT, df_TT_features, df_DX, df_DX_features, xgbr_clf, path="shap",
                  prefix="xgbr_structure_not_hot")
# get CV prediction (train, predict on validation fold)
cv_predictions = get_cv_predictions(df_TT_features, df_TT["CV"], df_DX_features, df_DX["CV"], xgbr_gs)
# do some vizualization
plots.target_decoy_comparison(cv_predictions)
#res_df, sfs, features = feature_selection_xgb(df_TT_features, df_TT, min_f=3, max_f=10)

# validate
df_TT_val, df_DX_val = process_csms(infile_val_loc)
df_TT_features_val, df_DX_features_val = process_features(df_TT_val, df_DX_val, one_hot, config)
df_TT_val["CV_predict"] = xgbr_clf.predict(df_TT_features_val)
df_DX_val["CV_predict"] = xgbr_clf.predict(df_DX_features_val)
df_val = pd.concat([df_TT_val, df_DX_val])
sns.jointplot(x="CV", y="CV_predict", data=df_val, kind="kde")
plt.show()

cv_predictions = get_cv_predictions(df_TT_features_val, df_TT_val["CV"],
                                    df_DX_features_val, df_DX_val["CV"], xgbr_gs)
sns.jointplot(x="Predicted CV", y="Observed CV", hue="Type", data=cv_predictions)
plt.show()