# How to use AI4Water for classification problems

from ai4water import Model
from ai4water.datasets import MtropicsLaos

data = MtropicsLaos().make_classification(lookback_steps=2)

model = Model(
    input_features=data.columns.tolist()[0:-1],
    output_features=data.columns.tolist()[-1],
    val_fraction=0.0,
    model={"DecisionTreeClassifier": {"max_depth": 4}},
)

h = model.fit(data=data)

# make prediction on test data
p = model.predict()
#
# # get some useful plots
model.interpret()

model.view()

# # **********Evaluate the model on test data using only input
x, y = model.test_data()
pred = model.predict(x=x)  # using only `x`
