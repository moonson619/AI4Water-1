
from typing import Union, List, Dict

from ai4water.preprocessing.transformations import Transformation

import numpy as np
import pandas as pd


class Transformations(object):
    """
    While the [Transformation][ai4water.preprocessing.transformations.Transformation]
    class is useful to apply a single transformation to a single data source, this
    class is helpful to apply multple transformations to a single data or multiple
    transformations to multiple data. This class is especially designed to be applied
    as part of `model` inside the `fit`, `predict` or `evaluate` methods. The
    `fit_transform` method should be applied before feeding the data to the
    algorithm and `inverse_transform` method should be called after algorithm has
    worked with data.

    Examples:
        >>> import numpy as np
        >>> from ai4water.preprocessing.transformations import Transformations
        >>> x = np.arange(50).reshape(25, 2)
        >>> transformer = Transformations(['a', 'b'], config=['minmax', 'zscore'])
        >>> x_ = transformer.fit_transform(x)
        >>> _x = transformer.inverse_transform(x_)

        Apply multiple transformations on multiple arrays which are passed as list
        >>> transformer = Transformations([['a', 'b'], ['a', 'b']],
                                      config=['minmax', 'zscore'])
        >>> x1 = np.arange(50).reshape(25, 2)
        >>> x2 = np.arange(50, 100).reshape(25, 2)
        >>> x1_ = transformer.fit_transform([x1, x2])
        >>> _x1 = transformer.inverse_transform(x1_)

        We can also do more complicated stuff as following
        >>> transformer = Transformations({'x1': ['a', 'b'], 'x2': ['a', 'b']},
                                      config={'x1': ['minmax', 'zscore'],
                                              'x2': [{'method': 'log', 'features': ['a', 'b']},
                                                     {'method': 'robust', 'features': ['a', 'b']}]
                                              })
        >>> x1 = np.arange(20).reshape(10, 2)
        >>> x2 = np.arange(100, 120).reshape(10, 2)
        >>> x = {'x1': x1, 'x2': x2}
        >>> x_ = transformer.fit_transform(x)
        >>> _x = transformer.inverse_transform(x_)

        In above example we apply `minmax` and `zscore` transformations on x1
        and `log` and `robust` transformations on x2 array
    """
    def __init__(
            self,
            feature_names: Union[list, dict],
            config: Union[str, list, dict] = None,
    ):
        """
        Arguments:
            feature_names:
                names of features in data
            config:
                Determines the type of transformation to be applied on data.

        """
        self.names = feature_names
        self.config = config

        self.scalers = {}

    def transformation(self, data):
        config = self.config

        if isinstance(data, list):
            if isinstance(config, str):
                config = [config for _ in range(len(data))]
        elif isinstance(data, dict):
            if isinstance(config, str):
                config = {k:config for k in data.keys()}

        return config

    def _check_features(self):

        if self.is_numpy_:
            assert self.names.__class__.__name__ == 'list', f"""
            feature_names are of type {type(self.names)}"""

        elif self.is_list_:
            for n in self.names:
                assert n.__class__.__name__ == 'list', f"""
                feature_names {type(self.names)} don't match data"""

        elif self.is_dict_:
            assert isinstance(self.names, dict), f"""
            feature_names are of type {type(self.names)}"""
            for src_name, n in self.names.items():
                assert n.__class__.__name__ == 'list'

        return

    def fit_transform(self, data:Union[np.ndarray, List, Dict]):
        """Transforms the data according the the `config`.

        Arguments:
            data:
                The data on which to apply transformations. It can be one of following

                - a (2d or 3d) numpy array
                - a list of numpy arrays
                - a dictionary of numpy arrays
        Returns:
            The transformed data which has same type and dimensions as the input data
        """
        if self.config is None:  # if no transformation then just return the data as it is
            return data

        orignal_data_type = data.__class__.__name__
        setattr(self, 'is_numpy_', False)
        setattr(self, 'is_list_', False)
        setattr(self, 'is_dict_', False)
        if isinstance(data, np.ndarray):
            setattr(self, 'is_numpy_', True)
        elif isinstance(data, list):
            setattr(self, 'is_list_', True)
        elif isinstance(data, dict):
            setattr(self, 'is_dict_', True)
        else:
            raise ValueError

        # first unpack the data if required
        self._check_features()

        # then apply transformation
        data = self._fit_transform(data)

        # now pack it in original form
        assert data.__class__.__name__ == orignal_data_type, f"""
        type changed from {orignal_data_type} to {data.__class__.__name__}
        """

        #self._assert_same_dim(self, orignal_data, data)

        return data

    def _transform_2d(self, data, columns, transformation=None, key="5"):
        """performs transformation on single data 2D source"""
        # it is better to make a copy here because all the operations on data happen after this.
        data = data.copy()
        scalers = {}
        if transformation:

            if isinstance(transformation, dict):
                data, scaler = Transformation(data=pd.DataFrame(data, columns=columns),
                                              **transformation)('transformation', return_key=True)
                scalers[key] = scaler

            # we want to apply multiple transformations
            elif isinstance(transformation, list):
                for idx, trans in enumerate(transformation):

                    if isinstance(trans, str):
                        data, scaler = Transformation(data=pd.DataFrame(data, columns=columns),
                                                      method=trans)('transformation', return_key=True)
                        scalers[f'{key}_{trans}_{idx}'] = scaler

                    elif trans['method'] is not None:
                        data, scaler = Transformation(data=pd.DataFrame(data, columns=columns),
                                                      **trans)('transformation', return_key=True)
                        scalers[f'{key}_{trans["method"]}_{idx}'] = scaler
            else:
                assert isinstance(transformation, str)
                data, scaler = Transformation(data=pd.DataFrame(data, columns=columns),
                                              method=transformation)('transformation', return_key=True)
                scalers[key] = scaler

            data = data.values

        self.scalers.update(scalers)

        return data

    def __fit_transform(self, data, feature_names, transformation=None, key="5"):
        """performs transformation on single data source
        In case of 3d array, the shape is supposed to be following
        (num_examples, time_steps, num_features)
        Therefore, each time_step is extracted and transfomred individually
        for example with time_steps of 2, two 2d arrays will be extracted and
        transformed individually
        (num_examples, 0,num_features), (num_examples, 1, num_features)
        """
        if data.ndim == 3:
            _data = np.full(data.shape, np.nan)
            for time_step in range(data.shape[1]):
                _data[:, time_step] = self._transform_2d(data[:, time_step],
                                                        feature_names,
                                                        transformation,
                                                        key=f"{key}_{time_step}")
        else:
            _data = self._transform_2d(data, feature_names, transformation, key=key)

        return _data

    def _fit_transform(self, data, key="5"):
        """performs transformation on every data source in data"""
        transformation = self.transformation(data)
        if self.is_numpy_:
            _data = self.__fit_transform(data, self.names, transformation, key)

        elif self.is_list_:
            _data = []
            for idx, array in enumerate(data):
                _data.append(self.__fit_transform(array,
                                                  self.names[idx],
                                                  transformation[idx],
                                                  key=f"{key}_{idx}")
                             )
        else:
            _data = {}
            for src_name, array in data.items():
                _data[src_name] = self.__fit_transform(array,
                                                       self.names[src_name],
                                                       transformation[src_name],
                                                       f"{key}_{src_name}")
        return _data

    def inverse_transform(self, data):
        """inverse transforms data where data can be dictionary, list or numpy
        array.

        Arguments:
            data:
                the data which is to be inverse transformed. The output of
                `fit_transform` method.
        Returns:
            The original data which was given to `fit_transform` method.
        """
        return self._inverse_transform(data)

    def _inverse_transform(self, data, key="5"):

        transformation = self.transformation(data)

        if self.is_numpy_:
            data = self.__inverse_transform(data, self.names, transformation, key)

        elif self.is_list_:
            assert isinstance(data, list)
            _data = []
            for idx, src in enumerate(data):
                __data = self.__inverse_transform(src,
                                                 self.names[idx],
                                                 transformation[idx],
                                                 f'{key}_{idx}')
                _data.append(__data)
            data = _data

        elif self.is_dict_:
            assert isinstance(data, dict)
            _data = {}
            for src_name, src in data.items():
                _data[src_name] = self.__inverse_transform(src,
                                                          self.names[src_name],
                                                          transformation[src_name],
                                                          f'{key}_{src_name}')
            data = _data

        return data

    def __inverse_transform(self, data, feature_names, transformation, key="5"):
        """inverse transforms one data source which may 2d or 3d nd array"""
        if data.ndim == 3:
            _data = np.full(data.shape, np.nan)
            for time_step in range(data.shape[1]):
                _data[:, time_step] = self._inverse_transform_2d(data[:, time_step],
                                                        columns=feature_names,
                                                        transformation=transformation,
                                                        key=f"{key}_{time_step}")
        else:
            _data = self._inverse_transform_2d(data, feature_names, key, transformation)

        return _data

    def _inverse_transform_2d(self, data, columns, key, transformation):
        """inverse transforms one 2d array"""
        data = pd.DataFrame(data, columns=columns)

        if transformation is not None:
            if isinstance(transformation, str):

                if key not in self.scalers:
                    raise ValueError(f"""
                    key `{key}` for inverse transformation not found. Available keys are {list(self.scalers.keys())}""")

                scaler = self.scalers[key]
                scaler, shape, _key = scaler['scaler'], scaler['shape'], scaler['key']
                original_shape = data.shape

                data, dummy_features = conform_shape(data, shape)  # get data to transform
                transformed_data = scaler.inverse_transform(data)
                data = transformed_data[:, dummy_features:]  # remove the dummy data
                data = data.reshape(original_shape)

            elif isinstance(transformation, list):
                # idx and trans both in reverse form
                for idx, trans in reversed(list(enumerate(transformation))):
                    if isinstance(trans, str):
                        scaler = self.scalers[f'{key}_{trans}_{idx}']
                        scaler, shape, _key = scaler['scaler'], scaler['shape'], scaler['key']
                        data = Transformation(data=data, method=trans)(what='inverse', scaler=scaler)

                    elif trans['method'] is not None:
                        features = trans.get('features', columns)
                        # if any of the feature in data was transformed
                        if any([True if f in data else False for f in features]):
                            orig_cols = data.columns  # copy teh columns in the original df
                            scaler = self.scalers[f'{key}_{trans["method"]}_{idx}']
                            scaler, shape, _key = scaler['scaler'], scaler['shape'], scaler['key']
                            data, dummy_features = conform_shape(data, shape, features)  # get data to transform

                            transformed_data = Transformation(data=data, **trans)(what='inverse', scaler=scaler)
                            data = transformed_data[orig_cols]  # remove the dummy data

            elif isinstance(transformation, dict):

                if any([True if f in data else False for f in transformation['features']]):
                    orig_cols = data.columns
                    scaler = self.scalers[key]
                    scaler, shape, _key = scaler['scaler'], scaler['shape'], scaler['key']
                    data, dummy_features = conform_shape(data, shape, features=transformation['features'])
                    transformed_data = Transformation(data=data, **transformation)(what='inverse', scaler=scaler)
                    data = transformed_data[orig_cols]  # remove the dummy data
        return data


def conform_shape(data, shape, features=None):
    # if the difference is of only 1 dim, we resolve it
    if data.ndim > len(shape):
        data = np.squeeze(data, axis=-1)
    elif data.ndim < len(shape):
        data = np.expand_dims(data, axis=-1)

    assert data.ndim == len(shape), f"""original data had {len(shape)} wihle the 
    new data has {data.ndim} dimensions"""

    # how manu dummy features we have to add to match the shape
    dummy_features = shape[-1] - data.shape[-1]

    if data.__class__.__name__ in ['DataFrame', 'Series']:
        # we know what features must be in data, so put them in data one by one
        # if they do not exist in data already
        if features:
            for f in features:
                if f not in data:
                    data[f] = np.random.random(len(data))
        # identify how many features to be added by shape information
        elif dummy_features > 0:
            dummy_data = pd.DataFrame(np.random.random((len(data), dummy_features)))
            data = pd.concat([dummy_data, data], axis=1)
    else:
        dummy_data = np.random.random((len(data), dummy_features))
        data = np.concatenate([dummy_data, data], axis=1)

    return data, dummy_features