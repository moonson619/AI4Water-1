import copy
import importlib
from typing import Union

from .postprocessing.SeqMetrics import RegressionMetrics
from .utils.utils import dateandtime_now, jsonize, MATRIC_TYPES, update_model_config, TrainTestSplit


class ModelOptimizerMixIn(object):

    def __init__(
            self,
            model,
            algorithm,
            num_iterations,
            process_results,
            prefix="hpo",
            data=None
    ):
        self.model = model
        self.algorithm = algorithm
        self.num_iterations = num_iterations
        self.process_results = process_results
        self.prefix = prefix

        if isinstance(data, tuple) or isinstance(data, list):
            assert len(data) == 2
            self.xy = True
        else:
            self.xy = False

        self.data = data

    def fit(self):

        PREFIX = f"{self.prefix}_{dateandtime_now()}"
        self.iter = 0
        print("{:<15} {:<20}".format("Iteration No.",  "Validation Score"))

        hpo = importlib.import_module("ai4water.hyperopt")

        val_metric = self.model.val_metric
        metric_type = MATRIC_TYPES.get(val_metric, 'min')
        cross_validator = self.model.config['cross_validator']
        config = jsonize(self.model.config)

        def objective_fn(
                seed=None,
                **suggestions,
        ):
            config['seed'] = seed
            config['verbosity'] = -1
            config['prefix'] = PREFIX

            getattr(self, f'update')(config, suggestions)

            _model = self.model.from_config(
                config.copy(),
                make_new_path=True,
            )

            if cross_validator is None:

                if self.xy:  # todo, it is better to split data outside objective_fn
                    splitter = TrainTestSplit(*self.data, test_fraction=config['test_fraction'])
                    train_x, test_x, train_y, test_y = splitter.split_by_slicing()
                    _model.fit(x=train_x, y=train_y)
                    p = _model.predict(test_x)
                else:
                    _model.fit(data=self.data)
                    test_y, p = _model.predict(data='validation', return_true=True,
                                               process_results=False)

                metrics = RegressionMetrics(test_y, p)
                val_score = getattr(metrics, val_metric)()
            else:
                if self.xy:
                    val_score = _model.cross_val_score(*self.data)
                else:
                    val_score = _model.cross_val_score(data=self.data)

            del _model

            if metric_type != "min":
                val_score = 1.0 - val_score

            print("{:<15} {:<20.3f}".format(self.iter, val_score))
            self.iter += 1

            return val_score

        optimizer = hpo.HyperOpt(
            self.algorithm,
            objective_fn=objective_fn,
            param_space=self.space,
            num_iterations=self.num_iterations,
            process_results=self.process_results,
            opt_path=f"results\\{PREFIX}"
        )

        optimizer.fit()

        return optimizer


class OptimizeHyperparameters(ModelOptimizerMixIn):

    def __init__(
            self,
            model,
            space,
            algorithm,
            num_iterations,
            process_results=False,
            data=None,
            **kwargs
    ):
        super().__init__(
            model=model,
            algorithm=algorithm,
            num_iterations=num_iterations,
            process_results=process_results,
            data=data,
            prefix="hpo"
        )

        self.space = space
        config = jsonize(model.config)
        model_config = config['model']
        # algo type is name of algorithm, e.g. xgboost, randomforest or layers
        self.algo_type = list(model_config.keys())[0]
        self.original_model = model._original_model_config

    def update(self, config, suggestions):
        # first update the model config parameters
        new_model_config = update_model_config(self.original_model['model'].copy(), suggestions)
        config['model'] = {self.algo_type: new_model_config}

        # now update hyperparameters which are not part of model config
        new_other_config = update_model_config(self.original_model['other'].copy(), suggestions)
        config.update(jsonize(new_other_config))

        return config


class OptimizeTransformations(ModelOptimizerMixIn):

    def __init__(
            self,
            model,
            categories,
            num_iterations=12,
            algorithm="bayes",
            include=None,
            exclude=None,
            append=None,
            process_results=False,
            data=None,
    ):
        super().__init__(
            model=model,
            num_iterations=num_iterations,
            algorithm=algorithm,
            process_results=process_results,
            prefix="trans_hpo",
            data=data
        )

        self.space = make_space(self.model.input_features,
                                include=include,
                                exclude=exclude,
                                append=append,
                                categories=categories)

        self.input_features = model.input_features
        assert isinstance(self.input_features, list)
        self.output_features = model.output_features
        if isinstance(self.output_features, str):
            self.output_features = [self.output_features]
        assert len(self.output_features) == 1


    def update(self, config, suggestions):
        """updates `x_transformation` and `y_transformation` keys in config
        based upon `suggestions`."""
        transformations = []
        y_transformations = []

        for feature, method in suggestions.items():

            if method == "none":
                pass
            else:
                t = {"method": method, "features": [feature]}

                if method.startswith("log"):
                    t["treat_negatives"] = True
                    t["replace_zeros"] = True
                elif method in ["box-cox", "yeo-johnson", "power"]:
                    t["treat_negatives"] = True
                    t["replace_zeros"] = True
                elif method == "sqrt":
                    t['treat_negatives'] = True
                    t["replace_zeros"] = True

                if feature in self.input_features:
                    transformations.append(t)
                else:
                    y_transformations.append(t)

        # following parameters must be overwritten even if they were provided by the user.
        config['x_transformation'] = transformations
        config['y_transformation'] = y_transformations or None

        return


def make_space(
        input_features: list,
        categories: list,
        include: Union[str, list, dict] = None,
        exclude: Union[str, list] = None,
        append: dict = None,
) -> list:
    """
    Arguments:
        input_features :
        categories :
        include: the names of input features to include
        exclude: the name/names of input features to exclude
        append: the input features with custom candidate transformations
    """
    hpo = importlib.import_module("ai4water.hyperopt")
    Categorical = hpo.Categorical

    # although we need space as list at the end, it is better to create a dictionary of it
    # because manipulating dictionary is easier
    space = {
        name: Categorical(categories, name=name) for name in input_features
    }

    if include is not None:
        if isinstance(include, str):
            include = {include: categories}
        elif isinstance(include, list):
            _include = {}
            for feat in include:
                assert feat in input_features, f"{feat} is not in input_features but is used in include"
                if isinstance(feat, str):
                    _include[feat] = categories
                else:
                    assert isinstance(feat, dict) and len(feat) == 1
                    _include[list(feat.keys())[0]] = list(feat.values())[0]
            include = _include
        else:
            assert isinstance(include, dict) and len(include) == 1

        # since include is given, we will ignore default case when all features are considered
        space = {}
        for k, v in include.items():
            if not isinstance(v, Categorical):
                assert isinstance(v, list), f"space for {k} must be list but it is {v.__class__.__name__}"
                v = Categorical(v, name=k)
            space[k] = v

    if exclude is not None:
        if isinstance(exclude, str):
            exclude = [exclude]
        assert isinstance(exclude, list)
        for feat in exclude:
            space.pop(feat)

    if append is not None:
        assert isinstance(append, dict)
        for k, v in append.items():
            if not isinstance(v, Categorical):
                assert isinstance(v, list), f"space for {k} must be list but it is {v.__class__.__name__}"
                v = Categorical(v, name=k)
            space[k] = v

    return list(space.values())
