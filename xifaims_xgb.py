import argparse
import os
import pathlib
# import matplotlib.pyplot as plt
import pickle
import sys

import numpy as np
import pandas as pd
import xgboost
import yaml
from mlxtend.feature_selection import SequentialFeatureSelector as SFS
from scipy.stats import pearsonr
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline

from xifaims import parameters as xs
from sklearn.feature_selection import RFECV
from xifaims import processing as xp


def feature_hyperparameter_optimization(df_TT_features_train, df_TT_y, grid, feature="SSF"):
    """
    Run feature selectiona and parametergridsearch on  the training data. Use
    3 fold crossvalidation for both.

    Return the best_parameters, best_features and cv results

    Parameters:
    df_TT_features_train: df, training features
    df_TT_y: ar-like, target values
    """
    xgbr = xgboost.XGBRegressor()

    # use the parameteized feature selection technique
    if feature == "SFS":
        # %% this is the complete pipeline - feature selection and parameter optimization
        selector = SFS(xgbr, k_features="parsimonious", forward=True, floating=False,
                       verbose=0, scoring="neg_mean_squared_error", cv=3)
        # selector = RFECV(xgbr, step=1, cv=3, verbose=1)
        pipe = Pipeline([('sfs', selector), ('xgb', xgbr)])

    elif feature == "RFECV":
        # %% this is the complete pipeline - feature selection and parameter optimization
        selector = RFECV(xgbr, min_features_to_select=5, verbose=0,
                         scoring="neg_mean_squared_error", cv=3)
        pipe = Pipeline([('rfecv', selector), ('xgb', xgbr)])

    elif feature.lower() == "none":
        pipe = Pipeline([('xgb', xgbr)])

    # adapt parameters for clf
    param_grid = {f"xgb__{f}": value for f, value in xs.xgb_params[grid].items()}
    #param_grid = {f"xgb__{f}": value for f, value in {"n_estimators": [10, 50]}.items()}
    gs = GridSearchCV(estimator=pipe, param_grid=param_grid, scoring='neg_mean_squared_error',
                      n_jobs=-1, cv=3, refit=False, verbose=3, return_train_score=True)
    gs = gs.fit(df_TT_features_train, df_TT_y)

    # %% refit the estimator with the best parameters
    # apply again the feature selection to avoid calling refit in the grid search above
    pipe = pipe.set_params(**gs.best_params_).fit(df_TT_features_train, df_TT_y)

    if feature == "SFS":
        best_features = df_TT_features_train.columns[list(pipe.steps[0][1].k_feature_idx_)]

    elif feature == "RFECV":
        best_features = df_TT_features_train.columns[pipe.steps[0][1]._get_support_mask()]

    elif feature.lower() == "none":
        best_features = df_TT_features_train.columns

    summary_df = pd.DataFrame(gs.cv_results_)
    res_dic = {"best_features_gs": best_features, "summary_gs": summary_df,
               "best_params_gs": {i.replace("xgb__", ""): j for i, j in gs.best_params_.items()}}
    return res_dic


if __name__ == "__main__":
    # # parsing and options
    # results_dir = "results_dev"
    # infile_loc = "data/combined_8PMLunique_4PMLS_nonu.csv"
    # #infile_loc = "data/293T_DSSO_nonunique1pCSM.csv"
    # infile_val_loc = "data/26S_BS3_LS_nonunique1pCSM.csv"
    # config_loc = "parameters/faims_structure_selection.yaml"
    # config_loc = "parameters/faims_all.yaml"
    # one_hot = False
    # --one_hot -o results/dev_new/ -c "parameters/faims_all.yaml" --average --name 8PM4PM --infile "data/combined_8PMLunique_4PMLS_nonu.csv" --jobs 8
    # --xgb tiny -s -o results/dev_new/ -c "parameters/faims_all.yaml" --average --name 8PM4PM --infile "data/combined_8PMLunique_4PMLS_nonu.csv"
    #--xgb tiny -s -o results/dev_new/ -c "parameters/faims_all.yaml" --average --name 8PM4PM --infile "data/combined_8PMLunique_4PMLS_nonu.csv" --feature "none"
    # --xgb tiny -s -o results/dev_new/ -c "parameters/faims_all.yaml" --average --name 8PM4PM --infile "data/combined_8PMLunique_4PMLS_nonu.csv" --feature "RFECV"

    parser = argparse.ArgumentParser(description='Train XGBoost on CLMS data for FAIMS prediction.')
    parser.add_argument('--infile', type=pathlib.Path, required=True,
                        help='CSM data.')

    # options
    parser.add_argument('-e', '--one_hot', dest='one_hot', action='store_true',
                        help='Uses 1-hot encoding for charge state.')
    parser.add_argument('-n', '--continuous', dest='cont', action='store_true', default=False,
                        help='Uses continuous encoding for charge state.')
    parser.add_argument('-a', '--average', dest='average', action="store_true",
                        help='If set CV values are averaged for redundant CSMs. (pep1, pep2, z')

    parser.add_argument('-x', '--xgb', default='small', action="store",
                        help='XGB parameter grid. One of tiny, small, large, huge.')

    parser.add_argument('-f', '--feature', default='SSF', action="store",
                        help='Feature selection method, one of (SSF, RFECV, None).')

    # debug testing
    parser.add_argument('-s', '--sample', dest='sample', action='store_true', default=False,
                        help='Sample 10 columns for testing.')

    # input / output
    parser.add_argument('-o', '--output', default='outdir', action="store",
                        help='Output directory to store results.')

    parser.add_argument('-c', '--config', default='config', action="store",
                        help='Config file.')

    parser.add_argument('-m', '--name', default='config', action="store",
                        help='Basename that is used for storage.')

    parser.add_argument('-j', '--jobs', default=-1, action="store",
                        help='Number of jobs to use during grid search.')

    print(parser.parse_args())
    args = parser.parse_args().__dict__
    # %%
    prefix = os.path.basename(args["config"].split(".")[0]) + "-" + os.path.basename(
        str(args["infile"]).replace(".csv", ""))
    config = yaml.load(open(args["config"]), Loader=yaml.FullLoader)
    config["jobs"] = int(args["jobs"])
    print(config)
    dir_res = os.path.join(args["output"], prefix)
    if not os.path.exists(dir_res):
        os.makedirs(dir_res)

    if args["one_hot"] + args["cont"] == 2:
        print("error, charge cannot be one_hot and continous encoded at the same time.")
        sys.exit()

    if args["one_hot"]:
        one_hot = args["one_hot"]
    else:
        one_hot = 0

    if args["average"]:
        ycol = "mCV"
    else:
        ycol = "CV"
    # %% real processing
    # input data
    df_unique, df_nonunique = xp.process_csms(args["infile"], config)
    df_features = xp.process_features(df_unique, one_hot, config)

    df_TT, df_DX = df_unique[df_unique.isTT == True], df_unique[df_unique.isTT == False]
    df_TT = xp.charge_filter(df_TT, config["charge"])
    df_DX = xp.charge_filter(df_DX, config["charge"])
    # split into targets and decoys

    df_TT_features = df_features.loc[df_TT.index]
    df_DX_features = df_features.loc[df_DX.index]

    if args["sample"]:
        col = df_TT_features.sample(10, axis=1).columns
    else:
        col = df_TT_features.columns

    # get train and validation data
    training_idx, validation_idx = train_test_split(df_TT.index, test_size=0.2)
    df_TT_train, df_TT_val = df_TT.loc[training_idx], df_TT.loc[validation_idx]
    df_TT_features_train, df_TT_features_val = df_TT_features.loc[training_idx], \
                                               df_TT_features.loc[validation_idx]

    # get results
    results_dic = feature_hyperparameter_optimization(df_TT_features_train[col], df_TT_train[ycol],
                                                      grid=args["xgb"], feature=args["feature"])
    args["infile"] = str(args["infile"])
    results_dic["xifaims_params"] = args
    results_dic["xifaims_config"] = config

    # train again on all train data and predict test data
    xgbr = xgboost.XGBRegressor(**results_dic["best_params_gs"])
    xgbr.fit(df_TT_features_train[results_dic["best_features_gs"].values], df_TT_train[ycol])

    train_predictions = xgbr.predict(df_TT_features_train[results_dic["best_features_gs"].values])
    val_predictions = xgbr.predict(df_TT_features_val[results_dic["best_features_gs"].values])
    DX_predictions = xgbr.predict(df_DX_features[results_dic["best_features_gs"].values])

    # compute predictions
    df_predictions = pd.DataFrame()
    df_predictions["predictions"] = np.concatenate(
        [train_predictions, val_predictions, DX_predictions])
    df_predictions["observed"] = np.concatenate([df_TT_train[ycol].values, df_TT_val[ycol].values,
                                                 df_DX[ycol]])
    df_predictions["observed"] += np.random.normal(0, 0.5, df_predictions.shape[0])
    df_predictions["Split"] = np.repeat(["Train", "Test", "DX"],
                                        [len(train_predictions), len(val_predictions),
                                         len(DX_predictions)])

    # metrics df
    metrics_df = pd.DataFrame()
    metrics_n = ["r2", "pearsonr", "MAE", "MSE"]
    metrics_fn = [r2_score, pearsonr, mean_absolute_error, mean_squared_error]
    for mn, mfn in zip(metrics_n, metrics_fn):
        if mn == "pearsonr":
            metrics_df[mn] = [mfn(df_TT_train[ycol], train_predictions)[0],
                              mfn(df_TT_val[ycol], val_predictions)[0],
                              mfn(df_DX[ycol], DX_predictions)[0]]
        else:
            metrics_df[mn] = [mfn(df_TT_train[ycol], train_predictions),
                              mfn(df_TT_val[ycol], val_predictions),
                              mfn(df_DX[ycol], DX_predictions)]
    metrics_df["split"] = ["Train", "Validation", "DX"]

    # finalize data for storage
    print(results_dic.keys())
    results_dic["xgb"] = xgbr
    results_dic["predictions_df"] = df_predictions
    results_dic["data"] = {"TT_train": (df_TT_train, df_TT_features_train, train_predictions),
                           "TT_val": (df_TT_val, df_TT_features_val, val_predictions),
                           "DX": (df_DX, df_DX_features, DX_predictions)}
    results_dic["metrics"] = metrics_df.round(3)
    results_dic["df_unique"] = df_unique
    results_dic["df_nonunique"] = df_nonunique

    # store all as pickle
    pickle.dump(results_dic, open(os.path.join(args["output"], f"xifaims_{args['name']}.p"), "wb"))
    # what do we want to do
    # 1) plot cv perfomance
    # 2) plot train - validation performance
    # 3) plot shap
    # 4) plot shap interaction plot
    # 5) plot decoy
    #%%
    # fax = sns.jointplot(x="observed", y="predictions", hue="Split", data=df_predictions,
    #                     marker="+", s=75)
    # plt.show()
    print("Results written to: {}".format(args["output"]))
    print(args)
