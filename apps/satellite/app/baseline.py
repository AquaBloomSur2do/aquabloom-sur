class MeanBaseline:
    def __init__(self):
        self.mean_value = None

    def fit(self, y_train: list[float]) -> None:
        if not y_train:
            raise ValueError("Los datos de entrenamiento no pueden estar vacíos.")
        self.mean_value = sum(y_train) / len(y_train)

    def predict(self, num_samples: int) -> list[float]:
        if self.mean_value is None:
            raise RuntimeError("El modelo debe ser ajustado (fit) antes de predecir.")
        return [self.mean_value] * num_samples
    