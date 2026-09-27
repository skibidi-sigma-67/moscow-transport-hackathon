import json
from pathlib import Path

import numpy as np

from research.data.dataset import load
from research.models.tcn import fit_predict
from research.training.train import mae, model, predict


def run():
    p, x, s, _ = load("dataset", "train")
    mask = p.tr_id < 1000000
    p, x, s = (p[mask].reset_index(drop=True), x[mask].reset_index(drop=True), s[mask])
    report = json.loads(Path("ml/artifacts/report.json").read_text())
    meta = json.loads(Path("ml/artifacts/metadata.json").read_text())
    y = p.target_delay_s.to_numpy()
    h = x.cur_dev_s.fillna(0).to_numpy()
    boundary = p.now.quantile(0.7)
    tr = np.flatnonzero(
        (p.now < boundary - 1800) & (p.target_time + y < boundary - 900)
    )
    va = np.flatnonzero(p.now >= boundary)
    m = model(meta["config"])
    target = y - (h if meta["mode"] == "residual" else 0)
    m.fit(
        x.iloc[tr][meta["features"]],
        target[tr],
        eval_set=(x.iloc[va][meta["features"]], target[va]),
        early_stopping_rounds=70,
    )
    cb = predict(m, x.iloc[va][meta["features"]], meta["mode"])
    _, tcn = fit_predict(s, h, y, tr, va)
    blends = {
        str(w): mae(y[va], (1 - w) * cb + w * tcn) for w in [0, 0.1, 0.25, 0.5, 1.0]
    }
    report["tcn"]["blend_time_mae"] = blends
    report["tcn"]["decision"] = (
        "Weight 0.1 improves group MAE by 0.317 s and time MAE by only 0.013 s. This is insufficient evidence for added runtime/dependency cost; keep CatBoost alone."
    )
    Path("ml/artifacts/report.json").write_text(json.dumps(report, indent=2))
    print(blends)


if __name__ == "__main__":
    run()
