# Edge–Cloud Predictive Maintenance Architecture

## 1. High-Level Data Flow

Sensor → Adapter → Edge AI → Decision Engine → Alert
↓
Cloud RUL → Drift Detection → Retrain

---

## 2. System Overview

This system follows an event-driven Edge + Cloud architecture designed for:

- Real-time anomaly detection
- Long-term degradation modeling
- Automated maintenance decisioning
- Continuous model improvement

---

## 3. Component Breakdown

### 3.1 Sensor Layer

**Responsibility:**

- Generate raw telemetry
- Temperature
- Vibration
- Pressure
- Rotation speed
- Timestamp
- Machine ID

**Publishes to:** `sensor.raw`

---

### 3.2 Adapter Layer

**Responsibility:**

- Validate data (schema enforcement)
- Normalize / scale features
- Add metadata (load, operating mode)
- Standardize event format

**Publishes to:** `sensor.cleaned`

---

### 3.3 Edge AI (Anomaly Detection)

**Purpose:** Real-time detection of abnormal behavior.

**Characteristics:**

- Lightweight model
- Low latency
- Runs at edge device

**Consumes:** `sensor.cleaned`  
**Publishes:** `edge.anomaly`

---

### 3.4 Decision Engine

**Purpose:** Apply business rules.

**Logic Examples:**

- If anomaly severity = high → trigger alert
- If RUL < critical threshold → trigger alert

**Publishes:** `maintenance.alert`

---

### 3.5 Alert Layer

**Purpose:**

- Notify operators
- Create maintenance ticket
- Update dashboard

---

## 4. Cloud Intelligence Layer

### 4.1 Cloud RUL Service

**Purpose:** Predict remaining useful life.

**Characteristics:**

- Deep sequence model
- Rolling time window
- GPU-enabled inference

**Consumes:** `sensor.cleaned`  
**Publishes:** `cloud.rul`

---

### 4.2 Drift Detection

**Purpose:** Monitor data distribution shifts.

**Logic:**

- Compare recent window vs training distribution
- Trigger retraining if drift exceeds threshold

**Publishes:** `drift.alert`

---

### 4.3 Retraining Pipeline

**Triggered by:** `drift.alert`

**Steps:**

1. Pull historical data
2. Retrain models
3. Validate performance
4. Deploy new version
5. Publish `model.update`

---

## 5. Architectural Properties

- Fully event-driven
- Edge + Cloud separation
- Scalable microservices
- Drift-aware lifecycle
- Business-rule decoupled
- Model version controlled

---

## 6. Full Logical Flow

Raw Telemetry
↓
sensor.raw
↓
Adapter
↓
sensor.cleaned
↓
┌──────────────┬─────────────────┐
│ │ │
Edge AI Cloud RUL Drift Detection
│ │ │
edge.anomaly cloud.rul drift.alert
↓ ↓ ↓
→ Decision Engine → maintenance.alert
↓
Alert
