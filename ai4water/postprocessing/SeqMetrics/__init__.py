"""SeqMetrics, the module to calculate performance related to tabular/structured and sequential data.
The values in a sequence are not necessarily related.
"""

from ._main import Metrics
from ._regression import RegressionMetrics
from ._classification import ClassificationMetrics
from .utils import plot_metrics
