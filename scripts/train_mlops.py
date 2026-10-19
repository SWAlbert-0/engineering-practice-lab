"""Bounded, trusted linear training process; consumes JSON, never unpickles uploads."""
import json, os, sys
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
if os.name == 'posix':
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024 * 1024, 1536 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (35, 35))
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, log_loss, confusion_matrix

def main():
    v = json.load(sys.stdin)
    x = np.asarray(v['x'], dtype=float)
    y = np.asarray(v['y'], dtype=int)
    p = v['parameters']
    indices = np.arange(len(y))
    train, validation = train_test_split(indices, test_size=0.25, random_state=p['seed'], stratify=y)
    scaler = StandardScaler().fit(x[train])
    model = LogisticRegression(C=p['c'], max_iter=300, random_state=p['seed']).fit(scaler.transform(x[train]), y[train])
    prob = model.predict_proba(scaler.transform(x[validation]))[:, 1]
    pred = (prob >= 0.5).astype(int)
    metrics = {'accuracy': float(accuracy_score(y[validation], pred)), 'precision': float(precision_score(y[validation], pred, zero_division=0)), 'recall': float(recall_score(y[validation], pred, zero_division=0)), 'f1': float(f1_score(y[validation], pred, zero_division=0)), 'log_loss': float(log_loss(y[validation], prob, labels=[0, 1])), 'confusion_matrix': confusion_matrix(y[validation], pred, labels=[0, 1]).tolist(), 'train_rows': len(train), 'validation_rows': len(validation), 'iterations': int(model.n_iter_[0]), 'converged': bool(model.n_iter_[0] < 300)}
    reference = []
    for i in range(x.shape[1]):
        edges = np.unique(np.quantile(x[train, i], np.arange(0.1, 1, 0.1))).tolist()
        count = np.bincount(np.searchsorted(edges, x[train, i], side='right'), minlength=len(edges) + 1).tolist()
        reference.append({'edges': edges, 'counts': count})
    artifact = {'schema': 'lab-linear-v1', 'features': v['features'], 'mean': scaler.mean_.tolist(), 'scale': scaler.scale_.tolist(), 'coefficient': model.coef_[0].tolist(), 'intercept': float(model.intercept_[0]), 'threshold': 0.5, 'classes': [0, 1], 'reference': reference}
    json.dump({'artifact': artifact, 'metrics': metrics, 'split': {'train': train.tolist(), 'validation': validation.tolist()}}, sys.stdout, allow_nan=False)
if __name__ == '__main__':
    main()
