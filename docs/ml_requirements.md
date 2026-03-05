# Machine Learning Requirements

This document defines functional and performance requirements for ML components in the predictive maintenance system.

---

# 1. Anomaly Detection (Edge AI)

## 1.1 Objective

Detect abnormal sensor behavior in real time.

## 1.2 Model Type

- Unsupervised or semi-supervised
- No labeled failure data required
- Learns normal behavior distribution

## 1.3 Candidate Approaches

- Isolation Forest
- Autoencoder
- One-Class SVM
- Lightweight LSTM Autoencoder

## 1.4 Input

- Single timestamp feature vector
- Temperature
- Vibration
- Pressure
- Rotation speed
- Load
- Operating mode

## 1.5 Output

- Anomaly score (0–1)
- Boolean flag
- Triggered features (optional)
- Severity level

## 1.6 Performance Requirements

- Inference time: < 100 ms
- Edge deployable
- Low memory footprint

---

# 2. RUL Prediction (Cloud)

## 2.1 Objective

Predict remaining useful life (in hours).

## 2.2 Model Type

- Supervised regression
- Sequence-based model

## 2.3 Input

- Sliding window of 50 timesteps
- Multivariate time series
- Includes:
  - Temperature
  - Vibration
  - Pressure
  - Rotation speed
  - Load
  - Operating mode

## 2.4 Model Candidates

- LSTM
- GRU
- Temporal CNN
- Transformer encoder

## 2.5 Output

- Predicted hours remaining
- Confidence score
- Health status classification

## 2.6 Performance Requirements

- Sequence length: 50 timesteps
- GPU supported
- Batch inference capable
- Latency < 1 second per request

---

# 3. Drift Detection

## 3.1 Objective

Detect statistical shifts in sensor distribution over time.

## 3.2 Input

- Rolling window of 1000 samples
- Cleaned feature vectors

## 3.3 Techniques

- Kolmogorov–Smirnov test
- Population Stability Index (PSI)
- KL Divergence
- Wasserstein distance

## 3.4 Trigger Condition

- Drift metric > threshold
- Sustained deviation over defined window

## 3.5 Output

- Drift alert event
- Trigger retraining pipeline

---

# 4. Model Lifecycle Requirements

- Version control for models
- Ability to hot-swap models
- Automated retraining trigger
- Validation before deployment

---

# 5. Monitoring Metrics

## Anomaly Model

- False positive rate
- Precision / Recall (if labeled data available)

## RUL Model

- RMSE
- MAE
- NASA scoring function (if applicable)

## Drift System

- Drift frequency
- Retrain frequency
- Post-retrain improvement

---

# 6. Deployment Constraints

- Edge anomaly model must run without GPU
- Cloud RUL model may use GPU
- All services must be stateless
- Models must be containerized

---

This document defines the baseline ML design constraints for the predictive maintenance system.
