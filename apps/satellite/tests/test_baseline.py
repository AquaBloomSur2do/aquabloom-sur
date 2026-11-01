import pytest
from fastapi.testclient import TestClient

from app.baseline import MeanBaseline
from app.main import app

client = TestClient(app)

def test_mean_baseline_logic():
    baseline = MeanBaseline()
    baseline.fit([10.0, 20.0, 30.0])
    assert baseline.mean_value == 20.0
    
    preds = baseline.predict(3)
    assert preds == [20.0, 20.0, 20.0]

def test_mean_baseline_empty_train():
    baseline = MeanBaseline()
    with pytest.raises(ValueError):
        baseline.fit([])

def test_mean_baseline_predict_without_fit():
    baseline = MeanBaseline()
    with pytest.raises(RuntimeError):
        baseline.predict(1)

def test_baseline_api_endpoint():
    payload = {
        "y_train": [5.0, 15.0],
        "num_predictions": 4
    }
    response = client.post("/api/v1/baseline", json=payload)
    
    assert response.status_code == 200
    assert response.json() == {"predictions": [10.0, 10.0, 10.0, 10.0]}
    