
import unittest

import numpy as np

from ai4water.postprocessing.SeqMetrics import ClassificationMetrics


predictions = np.array([[0.25, 0.25, 0.25, 0.25],
                        [0.01, 0.01, 0.01, 0.96]])
targets = np.array([[0, 0, 0, 1],
                    [0, 0, 0, 1]])


class TestClassificationMetrics(unittest.TestCase):

    def test_ce(self):
        class_metrics = ClassificationMetrics(targets, predictions, multiclass=True)
        # https://stackoverflow.com/a/47398312/5982232
        self.assertAlmostEqual(class_metrics.cross_entropy(), 0.71355817782)
        return

    def test_class_all(self):
        class_metrics = ClassificationMetrics(targets, predictions, multiclass=True)
        all_metrics = class_metrics.calculate_all()
        assert len(all_metrics) > 1
        return

    def test_accuracy(self):
        t = np.array([True, False, False, False])
        p = np.array([True, True, True, True])
        val_score = ClassificationMetrics(t,p).accuracy()
        self.assertAlmostEqual(val_score, 0.25)

        t = np.array([1, 0, 0, 0])
        p = np.array([1, 1, 1, 1])
        val_score = ClassificationMetrics(t, p).accuracy()
        self.assertAlmostEqual(val_score, 0.25)
        return

    def test_f1_score(self):
        t = np.array([1, 0, 0, 0])
        p = np.array([1, 1, 1, 1])
        f1_score = ClassificationMetrics(t, p).f1_score()
        return

if __name__ == "__main__":
    unittest.main()