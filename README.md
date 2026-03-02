# 🏭 Predictive Maintenance System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![TensorFlow 2.13](https://img.shields.io/badge/TensorFlow-2.13-orange.svg)](https://www.tensorflow.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Real-time predictive maintenance system with **edge AI**, **RUL prediction**, **drift detection**, and **adaptive retraining**.

---

## 🎯 Features

✅ **Edge Anomaly Detection** - Real-time detection with <100ms latency  
✅ **RUL Prediction** - LSTM-based remaining useful life estimation  
✅ **Drift Detection** - Automatic concept drift monitoring  
✅ **Adaptive Retraining** - Self-healing system with model updates  
✅ **Event-Driven Architecture** - RabbitMQ message broker  
✅ **Real-time Dashboard** - Live monitoring with Streamlit  
✅ **Edge/Cloud Separation** - Simulated distributed architecture

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         EDGE LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  Sensor Simulator → Data Adapter → Edge Anomaly Detector        │
│         ↓               ↓                    ↓                   │
│    sensor.raw    sensor.cleaned      edge.anomaly               │
└─────────────────────────────┬───────────────────────────────────┘
                              │ Edge-to-Cloud Bridge
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        CLOUD LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  RUL Predictor → Drift Detector → Retrain Service               │
│         ↓              ↓                ↓                        │
│    cloud.rul     drift.alert     model.update                   │
│                        ↓                                         │
│              Decision Engine → Alert Manager                     │
│                        ↓                                         │
│                   Dashboard UI                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠 Tech Stack

| Component           | Technology                     |
| ------------------- | ------------------------------ |
| **Language**        | Python 3.10+                   |
| **Message Broker**  | RabbitMQ 3.x                   |
| **ML Framework**    | TensorFlow/Keras, Scikit-learn |
| **Dashboard**       | Streamlit                      |
| **Data Processing** | Pandas, NumPy                  |
| **Visualization**   | Matplotlib, Plotly, Seaborn    |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Docker Desktop (for RabbitMQ)
- 4GB RAM minimum
- 2GB free disk space

### 1. Clone Repository

```bash
git clone https://github.com/ayushsingh08-ds/predictive-maintenance-system.git
cd predictive-maintenance-system
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings (optional - defaults work fine)
nano .env  # or use your preferred editor
```

### 4. Start RabbitMQ

```bash
# Start Cloud RabbitMQ
docker run -d \
  --name rabbitmq-cloud \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=admin123 \
  rabbitmq:3-management

# Start Edge RabbitMQ (for edge/cloud simulation)
docker run -d \
  --name rabbitmq-edge \
  -p 5673:5672 \
  -p 15673:15672 \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=admin123 \
  rabbitmq:3-management

# Verify RabbitMQ is running
# Cloud: http://localhost:15672 (admin/admin123)
# Edge: http://localhost:15673 (admin/admin123)
```

### 5. Run the System

**Option A: Run Everything (Automated)**

```bash
chmod +x scripts/run_full_system.sh
./scripts/run_full_system.sh
```

**Option B: Run Components Separately**

```bash
# Terminal 1: Edge Services
python edge/simulator/sensor_simulator.py &
python edge/adapter/data_adapter.py &
python edge/ai/anomaly_detector.py

# Terminal 2: Cloud Services
python messaging/bridge.py &
python cloud/ai/rul_predictor.py &
python cloud/services/drift_detector.py &
python cloud/services/decision_engine.py &
python cloud/services/retrain_service.py

# Terminal 3: Dashboard
streamlit run dashboard/app.py
```

### 6. Access Dashboard

Open browser to: **http://localhost:8501**

---

## 📁 Project Structure

```
predictive-maintenance-system/
│
├── config/                    # Configuration and schemas
│   ├── settings.py           # Centralized configuration
│   ├── event_schema.py       # Event data structures
│   └── topics.py             # RabbitMQ topic definitions
│
├── edge/                      # Edge layer services
│   ├── simulator/            # Sensor data simulation
│   │   ├── sensor_simulator.py
│   │   └── failure_scenarios.py
│   ├── adapter/              # Data normalization
│   │   └── data_adapter.py
│   └── ai/                   # Edge AI services
│       ├── anomaly_detector.py
│       └── models/           # Trained models
│
├── cloud/                     # Cloud layer services
│   ├── ai/                   # Cloud AI services
│   │   ├── rul_predictor.py
│   │   ├── drift_detector.py
│   │   └── model_registry/   # Model storage
│   └── services/             # Business logic
│       ├── decision_engine.py
│       ├── retrain_service.py
│       └── alert_manager.py
│
├── dashboard/                 # Web dashboard
│   ├── app.py                # Main dashboard
│   └── components/           # UI components
│
├── messaging/                 # Message broker clients
│   ├── rabbitmq_client.py    # RabbitMQ wrapper
│   ├── publisher.py          # Generic publisher
│   ├── consumer.py           # Generic consumer
│   └── bridge.py             # Edge-to-cloud bridge
│
├── notebooks/                 # Jupyter notebooks
│   ├── 01_eda.ipynb          # Exploratory analysis
│   ├── 02_anomaly_training.ipynb
│   ├── 03_rul_training.ipynb
│   └── 04_drift_analysis.ipynb
│
├── data/                      # Data storage
│   ├── raw/                  # Raw sensor data
│   ├── processed/            # Processed data
│   ├── models/               # Model artifacts
│   └── logs/                 # System logs
│
├── scripts/                   # Utility scripts
│   ├── setup_rabbitmq.sh     # RabbitMQ setup
│   ├── generate_test_data.py # Data generation
│   └── run_full_system.sh    # System launcher
│
├── tests/                     # Unit tests
│   ├── test_edge/
│   ├── test_cloud/
│   └── test_messaging/
│
├── docs/                      # Documentation
│   ├── architecture.md
│   ├── ml_requirements.md
│   └── deployment_guide.md
│
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

---

## 🎓 Key Concepts

### Event-Driven Architecture

The system uses **RabbitMQ topics** for communication:

| Topic               | Description                 |
| ------------------- | --------------------------- |
| `sensor.raw`        | Raw sensor readings         |
| `sensor.cleaned`    | Normalized sensor data      |
| `edge.anomaly`      | Anomaly detection results   |
| `cloud.rul`         | RUL predictions             |
| `drift.alert`       | Concept drift alerts        |
| `maintenance.alert` | Maintenance recommendations |
| `model.update`      | Model deployment events     |

### ML Models

1. **Anomaly Detection** (Edge)
   - Algorithm: Isolation Forest
   - Inference: <100ms
   - Threshold: 0.7

2. **RUL Prediction** (Cloud)
   - Algorithm: LSTM
   - Input: 50 timesteps
   - Output: Hours until failure

3. **Drift Detection** (Cloud)
   - Methods: KS test, PSI
   - Window: 1000 samples
   - Triggers retraining

---

## 🧪 Testing

### Run All Tests

```bash
pytest tests/ -v --cov=.
```

### Test Specific Component

```bash
# Edge services
pytest tests/test_edge/

# Cloud services
pytest tests/test_cloud/

# Messaging
pytest tests/test_messaging/
```

### Manual Testing Scenarios

```bash
# Normal operation
python edge/simulator/sensor_simulator.py --mode=normal

# Inject anomaly
python edge/simulator/sensor_simulator.py --mode=failing

# Gradual degradation
python edge/simulator/sensor_simulator.py --mode=degrading
```

---

## 📈 Performance Metrics

| Metric                 | Target    | Actual    |
| ---------------------- | --------- | --------- |
| Edge anomaly detection | <100ms    | ~50ms     |
| RUL prediction         | <500ms    | ~200ms    |
| End-to-end latency     | <2s       | ~1.2s     |
| Throughput             | 100 msg/s | 150 msg/s |
| Memory usage           | <2GB      | ~1.5GB    |

---

## 🔧 Configuration

Key settings in `.env`:

```bash
# Anomaly detection
ANOMALY_THRESHOLD=0.7

# RUL prediction
RUL_CRITICAL_HOURS=24
RUL_WARNING_HOURS=72

# Drift detection
DRIFT_THRESHOLD_PSI=0.3

# Retraining
RETRAIN_ON_DRIFT=true
RETRAIN_MIN_SAMPLES=500
```

---

## 🐛 Troubleshooting

### RabbitMQ Connection Failed

```bash
# Check if RabbitMQ is running
docker ps | grep rabbitmq

# Restart RabbitMQ
docker restart rabbitmq-cloud rabbitmq-edge

# Check logs
docker logs rabbitmq-cloud
```

### Dashboard Not Loading

```bash
# Check if port 8501 is available
lsof -i :8501

# Try different port
streamlit run dashboard/app.py --server.port 8502
```

### Model Not Found

```bash
# Train models first
python notebooks/02_anomaly_training.ipynb
python notebooks/03_rul_training.ipynb

# Or use pre-trained models
python scripts/download_models.py
```

---

## 🚢 Deployment

### Docker Deployment (Coming Soon)

```bash
docker-compose up -d
```

### Cloud Deployment

See [docs/deployment_guide.md](docs/deployment_guide.md) for AWS/GCP/Azure deployment instructions.

---

## 👥 Team

- **AI/ML Engineer** - Model training, drift detection, retraining
- **Platform Engineer** - Infrastructure, integration, dashboard

---

## 📅 Development Timeline

✅ Week 1: Core pipeline (sensor → adapter → anomaly → alert)  
✅ Week 2: RUL prediction, drift detection, dashboard, retraining

**Total:** 14-day sprint

---

## 🔮 Future Improvements

- [ ] Multi-sensor support
- [ ] Advanced ensemble models
- [ ] Kubernetes deployment
- [ ] Real-time model explainability
- [ ] Mobile dashboard
- [ ] Database persistence
- [ ] Alert escalation workflows
- [ ] A/B testing for models

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built as a demonstration of production-ready MLOps practices combining:

- Real-time stream processing
- Edge/Cloud hybrid architecture
- Adaptive machine learning
- Event-driven microservices

---

## 📞 Contact

**GitHub:** [@ayushsingh08-ds](https://github.com/ayushsingh08-ds)

For questions or issues, please open a GitHub issue.

---

## ⭐ Star This Repo

If you find this project useful, please give it a star! ⭐

---

**Built with ❤️ in 14 days**
