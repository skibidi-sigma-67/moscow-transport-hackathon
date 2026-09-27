# moscow-transport-hackathon
ML-предиктор задержек городского транспорта на основе потоковой телеметрии NDTP. Решение для Хакатона Московского транспорта.

## ML-модель

Обученные CatBoost-модели, PyTorch TCN-эксперимент, HTTP API и сабмит находятся в `ml/`.
Инструкция: [ml/README.md](ml/README.md). Результаты независимого test и ограничения:
[ml/reports/RESULTS.md](ml/reports/RESULTS.md). Полный backend + ML запускается через
`docker compose -f compose.ml.yaml up --build` (нужен работающий Docker daemon).
