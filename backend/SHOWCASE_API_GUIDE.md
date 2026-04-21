## Scenario Showcase API Guide

The backend now provides a dedicated **Showcase API** to display interactive demos of manufacturing scenarios. Each scenario is pre-configured with display preferences, key metrics, and demonstration instructions.

### How It Works

#### 1. **List Available Scenarios**

```bash
GET /scenarios
```

Response includes showcase configuration for each scenario:

```json
{
  "scenarios": [
    {
      "scenario_id": "routing_competition",
      "name": "Routing Competition",
      "description": "Parallel machines with unequal transport and processing...",
      "showcase_config": {
        "display_type": "routing_policy_demo",
        "highlight_metrics": ["routing_decisions", "machine_utilization", "path_times"],
        "showcase_title": "Routing Policy Comparison",
        "showcase_description": "Switch between least_loaded, round_robin, random...",
        "policy_steps": [
          {
            "policy": "least_loaded",
            "description": "Jobs go to machine with lowest current load."
          },
          ...
        ]
      }
    }
  ]
}
```

#### 2. **Load a Scenario**

```bash
POST /scenarios/load
Content-Type: application/json

{
  "scenario_id": "routing_competition"
}
```

This loads the scenario layout and **auto-resumes simulation**.

#### 3. **Fetch Showcase Data (Live)**

```bash
GET /showcase/routing_competition
```

Returns everything needed for the frontend showcase view:

```json
{
  "scenario_id": "routing_competition",
  "showcase_config": { ... },
  "graph": {
    "nodes": [ ... ],
    "edges": [ ... ]
  },
  "metrics": {
    "environment_time": 45.2,
    "throughput_hr": 312.5,
    "cycle_time_s": 3.8,
    "lead_time_m": 0.95,
    "wip": 8,
    "bottlenecks": 1,
    "oee_pct": 67.3,
    "avg_util_pct": 52.4,
    ...
  },
  "routing": {
    "active_policy": "least_loaded",
    "supported_policies": ["least_loaded", "random", "round_robin", "lowest_transport_time"],
    "simulation_ready": true
  },
  "machine_loads": [
    {
      "machine_id": "machine-a",
      "utilization": 0.45,
      "state": "Busy",
      "busy_time": 23.5,
      "downtime": 0.0
    },
    ...
  ]
}
```

### Frontend Integration (Flutter Example)

The repository includes `SHOWCASE_FLUTTER_EXAMPLE.dart` with a complete example widget:

**Key Features:**

- Auto-refresh metrics every 1 second via polling
- Display 6 KPI cards (Throughput, Cycle Time, Lead Time, WIP, OEE, Avg Util)
- Machine load bars with color coding (green <65%, orange 65-85%, red >85%)
- Interactive policy switcher with live effect visualization
- Graph layout display with node/edge counts

**Usage:**

```dart
ScenarioShowcase(scenarioId: 'routing_competition')
```

**Polling Pattern:**

```dart
Timer.periodic(Duration(seconds: 1), (_) {
  final response = await http.get(
    Uri.parse('http://127.0.0.1:8010/showcase/routing_competition')
  );
  final data = jsonDecode(response.body);
  setState(() { showcaseData = data; });
});
```

### Available Scenarios & Display Types

1. **balanced_baseline** (kpi_dashboard)
   - Standard production line with normal flow
   - Focus: Baseline KPI values
   - Highlight: throughput_hr, cycle_time_s, oee_pct

2. **bottleneck_stress** (bottleneck_monitor)
   - High arrival rate → queue pressure
   - Focus: WIP growth, queue buildup
   - Highlight: wip, bottlenecks, throughput_hr
   - Expected: WIP increases rapidly; bottleneck_count > 0

3. **failure_prone** (alert_dashboard)
   - Aggressive failure/maintenance behavior
   - Focus: Downtime alerts and recovery
   - Highlight: alerts, oee_pct, availability
   - Expected: Frequent alerts; oee drops then recovers

4. **routing_competition** (routing_policy_demo)
   - 3 parallel machines; unequal processing & transport times
   - Focus: Policy impact on load balance
   - Highlight: routing_decisions, machine_utilization, path_times
   - **Interactive:** Switch policies and observe utilization rebalancing
   - Policy Steps:
     - least_loaded: Prefers empty machines
     - round_robin: Alternates through machines
     - random: Unpredictable distribution
     - lowest_transport_time: Prefers closest machines

### Real-Time Display Recommendations

**Update Interval:** 500ms to 1s (use `/showcase/{id}` polling)

**Key Metrics to Display:**

- Throughput (jobs/hour) — show trend
- Cycle Time (seconds) — show average of last 20 jobs
- Lead Time (minutes) — job arrival to completion
- WIP (count) — current jobs in queue
- Bottlenecks (count) — machines >85% utilization
- OEE (%) — Overall Equipment Effectiveness
- Avg Utilization (%) — average across all machines

**Machine Load Cards:**

- Machine ID
- Current utilization (%) with color bar
- State (Idle, Busy, Failed, Maintenance)
- Cumulative busy time & downtime

**Routing Policy Display:**

- Active policy badge
- Policy-specific description
- Clickable buttons to switch (triggers POST /routing/policy)
- Visual effect: Watch machine utilization rebalance in 1-2 seconds

### Example Flow (Routing Demo)

1. User loads app → calls GET /scenarios
2. User selects "Routing Competition" → POST /scenarios/load
3. Frontend renders ScenarioShowcase widget
4. Widget calls GET /showcase/routing_competition every 1s
5. Metrics dashboard updates live
6. User clicks "round_robin" → POST /routing/policy with {"policy": "round_robin"}
7. Within 1-2s, machine_loads reflect new policy effect
8. User observes load rebalancing in real-time

### Advanced: Custom Showcase Types

To add your own display type:

1. Add to scenario `showcase_config` in [main.py](main.py):

   ```python
   "showcase_config": {
     "display_type": "custom_view",
     "custom_field": "custom_value"
   }
   ```

2. In Flutter, match on display_type and render custom widget:
   ```dart
   switch (config['display_type']) {
     case 'routing_policy_demo':
       return _buildPolicySwitcher(...);
     case 'custom_view':
       return _buildCustomView(...);
   }
   ```

### Testing the Showcase API

```bash
# Load routing_competition
curl -X POST http://127.0.0.1:8010/scenarios/load \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"routing_competition"}'

# Get showcase data
curl http://127.0.0.1:8010/showcase/routing_competition | jq '.'

# Switch policy
curl -X POST http://127.0.0.1:8010/routing/policy \
  -H "Content-Type: application/json" \
  -d '{"policy":"round_robin"}'

# Get updated showcase
curl http://127.0.0.1:8010/showcase/routing_competition | jq '.routing, .machine_loads'
```

All done! Your scenarios are now ready for interactive frontend demonstration.
