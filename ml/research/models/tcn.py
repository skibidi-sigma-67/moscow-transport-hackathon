import numpy as np
import torch
from torch import nn


class TCN(nn.Module):
    def __init__(self):
        super().__init__()
        self.blocks = nn.ModuleList(
            [nn.Conv1d(6 if i == 0 else 16, 16, 3, dilation=2**i) for i in range(5)]
        )
        self.head = nn.Linear(17, 1)

    def forward(self, x, hint):
        for i, layer in enumerate(self.blocks):
            x = torch.relu(layer(torch.nn.functional.pad(x, (2 * 2**i, 0))))
        return (
            self.head(torch.cat([x[:, :, -1], hint[:, None] / 300], dim=1)).squeeze(1)
            * 300
            + hint
        )


def fit_predict(seq, hint, y, train, valid, epochs=70):
    torch.set_num_threads(1)
    torch.manual_seed(42)
    model = TCN()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.03)
    xs, hs, ys = (
        torch.tensor(seq),
        torch.tensor(hint, dtype=torch.float32),
        torch.tensor(y, dtype=torch.float32),
    )
    rng = np.random.default_rng(42)
    for _ in range(epochs):
        for batch in np.array_split(rng.permutation(train), max(1, len(train) // 128)):
            optimizer.zero_grad()
            loss = (model(xs[batch], hs[batch]) - ys[batch]).abs().mean()
            loss.backward()
            optimizer.step()
    model.eval()
    with torch.no_grad():
        prediction = model(xs[valid], hs[valid]).numpy()
    return (model, prediction)
