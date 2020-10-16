"""
Created on Wed Oct 14 22:57:36 2020

@author: hanjo

!autopep8 xifaims/ml.py -i
!isort xifaims/ml.py
!autoflake --in-place --remove-unused-variables xifaims/ml.py
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost
from mlxtend.feature_selection import SequentialFeatureSelector as SFS
from mlxtend.plotting import plot_sequential_feature_selection as plot_sfs
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler
from sklearn.metrics import make_scorer, mean_squared_error
from sklearn.svm import SVC, SVR
from xgboost_autotune import fit_parameters
from tensorflow import keras
from tensorflow.keras.layers import Dense, Dropout

# from xgboost_autotune import fit_parameters


def training(df_TT, df_TT_features, model="SVM", scale=True, model_args={}):
    """
    Perform training a with variable models on the data.

    Parameters
    ----------
    df_TT : TYPE
        DESCRIPTION.
    df_TT_features : TYPE
        DESCRIPTION.
    model : TYPE, optional
        DESCRIPTION. The default is "SVM".
    scale : TYPE, optional
        DESCRIPTION. The default is True.

    Returns
    -------
    TYPE
        DESCRIPTION.

    """
    # train, validation split
    training_idx, validation_idx = train_test_split(df_TT.index, test_size=0.1)

    # global scaler
    ss_train = MinMaxScaler().fit(df_TT_features.loc[training_idx])

    # x variable
    if scale:
        val_df = ss_train.transform(df_TT_features.loc[validation_idx])
        train_df = ss_train.transform(df_TT_features.loc[training_idx])

        train_df = pd.DataFrame(
            train_df, index=training_idx, columns=df_TT_features.columns)
        val_df = pd.DataFrame(val_df, index=validation_idx,
                              columns=df_TT_features.columns)
    else:
        val_df = df_TT_features.loc[validation_idx]
        train_df = df_TT_features.loc[training_idx]

    # y variable
    train_y = df_TT["CV"].loc[training_idx]
    val_y = df_TT["CV"].loc[validation_idx]

    # fit the baseline
    if model == "SVM":
        return SVR_baseline(train_df, train_y, val_df, val_y, model_args)

    elif model == "XGB":
        return XGB_model(train_df, train_y, val_df, val_y, model_args)

    elif model == "FNN":
        return FAIMSNETNN_model(train_df, train_y, val_df, val_y, model_args)
    
    
def format_summary(train_df, val_df, train_y, val_y, clf, clf_name, gs):
    """
    Create summary dataframes for classifier performance.

    Parameters
    ----------
    train_df : TYPE
        DESCRIPTION.
    val_df : TYPE
        DESCRIPTION.
    train_y : TYPE
        DESCRIPTION.
    val_y : TYPE
        DESCRIPTION.
    clf : TYPE
        DESCRIPTION.
    clf_name : TYPE
        DESCRIPTION.
    gs : TYPE
        DESCRIPTION.

    Returns
    -------
    df_results : TYPE
        DESCRIPTION.
    cv_res : TYPE
        DESCRIPTION.

    """
    # make predictions
    df_results = pd.DataFrame()
    df_results["CV_Train"] = np.concatenate([train_y, val_y])
    df_results["CV_Predict"] = np.concatenate([np.ravel(clf.predict(train_df)),
                                               np.ravel(clf.predict(val_df))])
    df_results["Set"] = np.concatenate([["Train"] * len(train_y), ["Test"] * len(val_y)])
    df_results["classifier"] = clf_name

    # format results
    cv_res = pd.DataFrame(gs.cv_results_)
    cv_res = cv_res.sort_values(by="rank_test_score", ascending=True).iloc[0]
    cv_res = pd.DataFrame(cv_res.filter(regex="split")).reset_index()
    cv_res.columns = ["cv_split", "mse"]
    cv_res["split"] = cv_res["cv_split"].str.split("_").str[1]
    cv_res["classifier"] = clf_name
    return df_results, cv_res


def mle_feature_selection():
    """Feature selectionw rapper using sequential forward selection from MLE."""
    # feature selection
    xgbr = xgboost.XGBRFRegressor(**xgbr1.get_params())

    sfs = SFS(xgbr, k_features=8, forward=True,
              floating=False, scoring='neg_mean_squared_error', cv=3, n_jobs=-1)
    sfs = sfs.fit(train_df, train_y)

    features = pd.DataFrame.from_dict(sfs.get_metric_dict()).T
    print(features)

    fig1 = plot_sfs(sfs.get_metric_dict(), kind='std_dev')
    plt.title('Sequential Forward Selection (w. StdDev)')
    plt.grid()
    plt.show()


def SVR_baseline(train_df, train_y, val_df, val_y, model_args={"jobs": 8, "type": "SVC"}, cv=3):
    """
    Fits a SVM baseline model with exhaustive parameter optimization.

    Parameters
    ----------
    train_df : TYPE
        DESCRIPTION.
    train_y : TYPE
        DESCRIPTION.
    val_df : TYPE
        DESCRIPTION.
    val_y : TYPE
        DESCRIPTION.

    Returns
    -------
    df_results : TYPE
        DESCRIPTION.
    cv_res : TYPE
        DESCRIPTION.

    """
    tuned_parameters = [{'kernel': ['rbf'], 'gamma': [1e-3, 1e-4], 'C': [1, 10, 100, 1000]},
                        {'kernel': ['linear'], 'C': [1, 10, 100, 1000]}]
    # grid search
    if model_args["type"] == "SVC":
        clf = SVC
        metric = "accuracy"
        
    elif model_args["type"] == "SVR":
        clf = SVR
        metric = "neg_mean_squared_error"
        
    gs = GridSearchCV(clf(), tuned_parameters, cv=cv, scoring=metric,
                      return_train_score=True, verbose=1, n_jobs=model_args["jobs"])
    gs.fit(train_df, train_y)

    # refit clf
    svc = clf(**gs.best_params_)
    svc.fit(train_df, train_y)

    # get summary results
    df_results, cv_res = format_summary(train_df, val_df, train_y, val_y, svc, model_args["type"],
                                        gs)
    cv_res["params"] = str(gs.best_params_)
    return df_results, cv_res, gs, svc


def create_model(n1, d1, lr, epochs=100, batch_size=32, input_dim=29):
    """Helper function for gridsearch with keras."""
    inputs = keras.Input(shape=(input_dim,))
    x = Dense(n1, activation="relu", kernel_regularizer="l2")(inputs)
    x = Dropout(d1)(x)

    x = Dense(int(n1* 0.75), activation="relu", kernel_regularizer="l2")(inputs)
    x = Dropout(d1)(x)

    x = Dense(int(n1* 0.50), activation="relu", kernel_regularizer="l2")(x)
    x = Dropout(d1)(x)

    x = Dense(int(n1* 0.1), activation="relu", kernel_regularizer="l2")(x)
    x = Dropout(d1)(x)
    outputs = Dense(1, activation="linear")(x)

    adam = keras.optimizers.Adam(learning_rate=lr)
    model = keras.Model(inputs, outputs, name="FAIMSnet")
    model.compile(optimizer=adam, loss="mean_squared_error")
    return model


def FAIMSNETNN_model(train_df, train_y, val_df, val_y, model_args, cv=3):
    """FIT neuralnetwork model."""
    input_dim = train_df.shape[1]
    if model_args["grid"] == "tiny":
        param_grid = {"n1": [100], "d1": [0.3, 0.1], "lr": [0.001, 0.01], "epochs": [50],
                      "batch_size": [32, 128], "input_dim": [input_dim]}        
    else:
        param_grid = {"n1": [100, 200, 500, 1000], "d1": [0.5, 0.3, 0.15, 0.1],
                      "lr": [0.0001, 0.001, 0.01, 0.1], "epochs": [50],
                      "batch_size": [16, 32, 64, 128], "input_dim": [input_dim]}
        
    model = keras.wrappers.scikit_learn.KerasRegressor(build_fn=create_model, verbose=0)

    gs = GridSearchCV(estimator=model, param_grid=param_grid, n_jobs=-1, cv=cv,
                      return_train_score=True, verbose=2)
    gsresults = gs.fit(train_df, train_y)

    # history = model.fit(train_df, train_y, validation_split=0.1, epochs=200, batch_size=16)

    gs.best_params_["epochs"] = 100
    model = create_model(**gs.best_params_)
    history = model.fit(train_df, train_y, validation_split=0.1, epochs=gs.best_params_["epochs"],
                        batch_size=gs.best_params_["batch_size"])

    df_results, cv_res = format_summary(train_df, val_df, train_y, val_y, model, "FNN", gsresults)
    cv_res["params"] = str(gs.best_params_)
    return df_results, cv_res, gs, model


def XGB_model(train_df, train_y, val_df, val_y, model_args={"jobs": 8, "grid": "small"}, cv=3):
    """
    Fits XGB model with exhaustive parameter optimization.

    Parameters
    ----------
    train_df : TYPE
        DESCRIPTION.
    train_y : TYPE
        DESCRIPTION.
    val_df : TYPE
        DESCRIPTION.
    val_y : TYPE
        DESCRIPTION.

    Returns
    -------
    df_results : TYPE
        DESCRIPTION.
    cv_res : TYPE
        DESCRIPTION.

    """
    if model_args["grid"] == "small":
        parameters = {'n_estimators': [50, 150, 250, 25],
                      'max_depth': [3, 6, 9, 12],
                      'learning_rate': [0.001, 0.01, 0.1, 0.3],
                      'subsample': [0.90],
                      'reg_alpha': [None],
                      'colsample_bytree': [0.7],
                      'min_child_weight': [1, 3],
                      'gamma': [0.0],
                      'nthread': [model_args["jobs"]],
                      'seed': [42]}

    elif model_args["grid"] == "tiny":
        parameters = {'n_estimators': [10, 50, 100],
                      'learning_rate': [0.001, 0.01, 0.1, 0.3],
                      'nthread': [model_args["jobs"]],
                      'seed': [42]}
    else:
        parameters = {'n_estimators': [30, 50, 70, 100, 150, 200, 300],
                      'max_depth': [3, 5, 7, 9],
                      'min_child_weight': [0.001, 0.1, 1, 5, 10, 20],
                      'min_samples_split': [1, 2, 5, 10, 20, 30],
                      'num_leaves': [15, 35, 50, 75, 100, 150],
                      'gamma': [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
                      'min_samples_leaf': [1, 2, 5, 10, 20, 30],
                      'min_child_samples': [2, 7, 15, 25, 45],
                      'min_split_gain': [0, 0.001, 0.1, 1, 5, 20],
                      'max_features': range(10, 25, 3),
                      'subsample': [i/10 for i in range(4, 10)],
                      'colsample_bytree': [i/10 for i in range(4, 10)],
                      'feature_fraction': [i/10 for i in range(4, 10)],
                      'reg_alpha': [1e-5, 1e-2, 0.1, 1, 25, 100],
                      'reg_lambda': [1e-5, 1e-2, 0.1, 1, 25, 100],
                      'nthread': [model_args["jobs"]],
                      'seed': [42]}
    # xgb model and grid search
    xgbr = xgboost.XGBRegressor()
    gs = GridSearchCV(estimator=xgbr, param_grid=parameters, cv=cv, n_jobs=1,
                      verbose=1, scoring="neg_mean_squared_error", return_train_score=True)
    gs.fit(train_df, train_y)

    # refit clf
    xgbr = xgboost.XGBRegressor(**gs.best_params_)
    xgbr.fit(train_df, train_y)

    df_results, cv_res = format_summary(
        train_df, val_df, train_y, val_y, xgbr, "XGB", gs)
    cv_res["params"] = str(gs.best_params_)
    return df_results, cv_res, gs, xgbr


def XGB_model_sequential(train_df, train_y, val_df, val_y):
    """
    Fit a XGB Model by sequentially testing set of parameters. Faster than XGB_model but less acc.

    Parameters
    ----------
    train_df : TYPE
        DESCRIPTION.
    train_y : TYPE
        DESCRIPTION.
    val_df : TYPE
        DESCRIPTION.
    val_y : TYPE
        DESCRIPTION.

    Returns
    -------
    df_results : TYPE
        DESCRIPTION.
    cv_res : TYPE
        DESCRIPTION.

    """
    # xgb model and grid search
    mse = make_scorer(mean_squared_error, greater_is_better=False)
    gs = fit_parameters(initial_model=xgboost.XGBRegressor(),
                        initial_params_dict={},
                        X_train=train_df,
                        y_train=train_y,
                        min_loss=0.01,
                        scoring=mse, n_folds=3)

    # xgb model and grid search dummy
    params = {i: [j] for i, j in gs.get_params().items()}
    xgbr = xgboost.XGBRegressor()
    gs = GridSearchCV(estimator=xgbr, param_grid=params,
                      cv=3, n_jobs=1,
                      verbose=1, scoring="neg_mean_squared_error",
                      return_train_score=True)
    gs.fit(train_df, train_y)

    # refit clf
    xgbr = xgboost.XGBRegressor(**gs.best_params_)
    xgbr.fit(train_df, train_y)

    df_results, cv_res = format_summary(train_df, val_df, train_y, val_y,
                                        xgbr, "XGB_sequential", gs)
    return df_results, cv_res, gs, xgbr
