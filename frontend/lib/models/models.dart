import 'dart:convert';
import 'package:flutter/material.dart';

enum LayoutNodeType {
  machine('Machine'),
  buffer('Buffer'),
  divider('Divider'),
  conveyor('Conveyor'),
  source('Source'),
  sink('Sink');

  final String value;
  const LayoutNodeType(this.value);

  static LayoutNodeType fromString(String value) {
    return LayoutNodeType.values.firstWhere(
      (e) => e.value.toLowerCase() == value.toLowerCase(),
      orElse: () => LayoutNodeType.machine,
    );
  }
}

class LayoutPosition {
  final double x;
  final double y;

  LayoutPosition({required this.x, required this.y});

  Map<String, dynamic> toJson() => {'x': x, 'y': y};

  factory LayoutPosition.fromJson(Map<String, dynamic> json) {
    return LayoutPosition(
      x: (json['x'] as num).toDouble(),
      y: (json['y'] as num).toDouble(),
    );
  }

  Offset toOffset() => Offset(x, y);

  factory LayoutPosition.fromOffset(Offset offset) {
    return LayoutPosition(x: offset.dx, y: offset.dy);
  }
}

class LayoutNode {
  final String id;
  final LayoutNodeType type;
  LayoutPosition position;
  final Map<String, dynamic> properties;
  final int queueSize;

  LayoutNode({
    required this.id,
    required this.type,
    required this.position,
    this.properties = const {},
    this.queueSize = 0,
  });

  Map<String, dynamic> toJson() => {
    'id': id,
    'type': type.value,
    'position': position.toJson(),
    'properties': properties,
  };

  factory LayoutNode.fromJson(Map<String, dynamic> json) {
    return LayoutNode(
      id: json['id'],
      type: LayoutNodeType.fromString(json['type']),
      position: LayoutPosition.fromJson(json['position']),
      properties: Map<String, dynamic>.from(json['properties'] ?? {}),
      queueSize: json['queue_size'] ?? 0,
    );
  }

  LayoutNode copyWith({
    String? id,
    LayoutNodeType? type,
    LayoutPosition? position,
    Map<String, dynamic>? properties,
    int? queueSize,
  }) {
    return LayoutNode(
      id: id ?? this.id,
      type: type ?? this.type,
      position: position ?? this.position,
      properties: properties ?? Map<String, dynamic>.from(this.properties),
      queueSize: queueSize ?? this.queueSize,
    );
  }
}

class LayoutEdge {
  final String fromNode;
  final String toNode;
  final double? transportTime;
  final Map<String, dynamic> properties;

  LayoutEdge({
    required this.fromNode,
    required this.toNode,
    this.transportTime,
    this.properties = const {},
  });

  Map<String, dynamic> toJson() => {
    'from_node': fromNode,
    'to_node': toNode,
    'transport_time': transportTime,
    'properties': properties,
  };

  factory LayoutEdge.fromJson(Map<String, dynamic> json) {
    return LayoutEdge(
      fromNode: json['from_node'],
      toNode: json['to_node'],
      transportTime: json['transport_time']?.toDouble(),
      properties: Map<String, dynamic>.from(json['properties'] ?? {}),
    );
  }
}

class LayoutGraph {
  final List<LayoutNode> nodes;
  final List<LayoutEdge> edges;

  LayoutGraph({required this.nodes, required this.edges});

  Map<String, dynamic> toJson() => {
    'nodes': nodes.map((n) => n.toJson()).toList(),
    'edges': edges.map((e) => e.toJson()).toList(),
  };

  factory LayoutGraph.fromJson(Map<String, dynamic> json) {
    return LayoutGraph(
      nodes: (json['nodes'] as List)
          .map((n) => LayoutNode.fromJson(n))
          .toList(),
      edges: (json['edges'] as List)
          .map((e) => LayoutEdge.fromJson(e))
          .toList(),
    );
  }

  static fromJsonString(String jsonStr) =>
      LayoutGraph.fromJson(jsonDecode(jsonStr));
}

typedef FactoryLayout = LayoutGraph;

enum MachineStatus {
  idle('Idle'),
  busy('Busy'),
  failed('Failed'),
  maintenance('Maintenance');

  final String label;
  const MachineStatus(this.label);

  static MachineStatus fromString(String value) {
    return MachineStatus.values.firstWhere(
      (e) => e.label.toLowerCase() == value.toLowerCase(),
      orElse: () => MachineStatus.idle,
    );
  }
}

class MachineMetrics {
  final String machineId;
  final MachineStatus status;
  final double healthIndex;
  final double remainingUsefulLife;
  final int queueLength;
  final int productionCount;
  final double oee;
  final double utilization;
  final double temperature;
  final double vibration;
  final double load;
  final double congestionRisk;
  final double energyTotal;
  final double carbonTotal;
  final double? scheduledMaintenance;

  MachineMetrics({
    required this.machineId,
    required this.status,
    required this.healthIndex,
    required this.remainingUsefulLife,
    required this.queueLength,
    required this.productionCount,
    required this.oee,
    this.utilization = 0.0,
    this.temperature = 0.0,
    this.vibration = 0.0,
    this.load = 0.0,
    this.congestionRisk = 0.0,
    this.energyTotal = 0.0,
    this.carbonTotal = 0.0,
    this.scheduledMaintenance,
  });

  factory MachineMetrics.fromJson(Map<String, dynamic> json) {
    return MachineMetrics(
      machineId: json['machine_id'] ?? json['id'] ?? '',
      status: MachineStatus.fromString(
        json['state'] ?? json['status'] ?? 'Idle',
      ),
      healthIndex:
          (json['health'] as num?)?.toDouble() ??
          (json['health_index'] as num?)?.toDouble() ??
          1.0,
      remainingUsefulLife:
          (json['remaining_useful_life'] as num?)?.toDouble() ??
          (json['rul'] as num?)?.toDouble() ??
          500.0,
      queueLength: json['queue_length'] ?? 0,
      productionCount: json['good_count'] ?? json['production_count'] ?? 0,
      oee: (json['oee'] as num?)?.toDouble() ?? 0.0,
      utilization: (json['utilization'] as num?)?.toDouble() ?? 0.0,
      temperature: (json['temperature'] as num?)?.toDouble() ?? 0.0,
      vibration: (json['vibration'] as num?)?.toDouble() ?? 0.0,
      load:
          (json['load_factor'] as num?)?.toDouble() ??
          (json['load'] as num?)?.toDouble() ??
          0.0,
      congestionRisk: (json['congestion_risk'] as num?)?.toDouble() ?? 0.0,
      energyTotal: (json['energy_total'] as num?)?.toDouble() ?? 0.0,
      carbonTotal: (json['carbon_total'] as num?)?.toDouble() ?? 0.0,
      scheduledMaintenance: (json['scheduled_maintenance'] as num?)?.toDouble(),
    );
  }

  MachineMetrics copyWith({
    String? machineId,
    MachineStatus? status,
    double? healthIndex,
    double? remainingUsefulLife,
    int? queueLength,
    int? productionCount,
    double? oee,
    double? utilization,
    double? temperature,
    double? vibration,
    double? load,
    double? congestionRisk,
    double? scheduledMaintenance,
  }) {
    return MachineMetrics(
      machineId: machineId ?? this.machineId,
      status: status ?? this.status,
      healthIndex: healthIndex ?? this.healthIndex,
      remainingUsefulLife: remainingUsefulLife ?? this.remainingUsefulLife,
      queueLength: queueLength ?? this.queueLength,
      productionCount: productionCount ?? this.productionCount,
      oee: oee ?? this.oee,
      utilization: utilization ?? this.utilization,
      temperature: temperature ?? this.temperature,
      vibration: vibration ?? this.vibration,
      load: load ?? this.load,
      congestionRisk: congestionRisk ?? this.congestionRisk,
      scheduledMaintenance: scheduledMaintenance ?? this.scheduledMaintenance,
    );
  }
}

class GlobalMetrics {
  final double environmentTime;
  final int machineCount;
  final double oee;
  final double availability;
  final double performance;
  final double quality;
  final int wip;
  final int completedJobs;
  final bool simulationEnabled;
  final double throughput;
  final double avgCycleTime;
  final double leadTime;
  final int bottlenecks;
  final List<String> bottleneckNodes;
  final double avgUtilization;
  final double totalEnergy;
  final double totalCarbon;

  GlobalMetrics({
    required this.environmentTime,
    required this.machineCount,
    required this.oee,
    required this.availability,
    required this.performance,
    required this.quality,
    required this.wip,
    required this.completedJobs,
    required this.simulationEnabled,
    this.throughput = 0.0,
    this.avgCycleTime = 0.0,
    this.leadTime = 0.0,
    this.bottlenecks = 0,
    this.bottleneckNodes = const [],
    this.avgUtilization = 0.0,
    this.totalEnergy = 0.0,
    this.totalCarbon = 0.0,
  });

  factory GlobalMetrics.fromJson(Map<String, dynamic> json) {
    final rawBottleneckNodes = json['bottleneck_nodes'];
    final parsedBottleneckNodes = rawBottleneckNodes is List
        ? rawBottleneckNodes
              .map((node) => node?.toString() ?? '')
              .where((node) => node.trim().isNotEmpty)
              .toList()
        : <String>[];

    return GlobalMetrics(
      environmentTime: (json['environment_time'] as num?)?.toDouble() ?? 0.0,
      machineCount: json['machine_count'] ?? 0,
      oee: (json['oee'] as num?)?.toDouble() ?? 0.0,
      availability: (json['availability'] as num?)?.toDouble() ?? 0.0,
      performance: (json['performance'] as num?)?.toDouble() ?? 0.0,
      quality: (json['quality'] as num?)?.toDouble() ?? 0.0,
      wip: json['wip'] ?? 0,
      completedJobs: json['completed_jobs'] ?? 0,
      simulationEnabled: json['simulation_enabled'] ?? false,
      throughput: (json['throughput_hr'] as num?)?.toDouble() ?? 0.0,
      avgCycleTime: (json['cycle_time_s'] as num?)?.toDouble() ?? 0.0,
      leadTime: (json['lead_time_m'] as num?)?.toDouble() ?? 0.0,
      bottlenecks: json['bottlenecks'] ?? 0,
      bottleneckNodes: parsedBottleneckNodes,
      avgUtilization: (json['avg_util'] as num?)?.toDouble() ?? 0.0,
      totalEnergy: (json['total_energy_kwh'] as num?)?.toDouble() ?? 0.0,
      totalCarbon: (json['total_carbon_kg'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class SimulationState {
  final bool ready;
  final bool enabled;
  final double speedMultiplier;
  final double environmentTime;

  SimulationState({
    required this.ready,
    required this.enabled,
    required this.speedMultiplier,
    required this.environmentTime,
  });

  factory SimulationState.fromJson(Map<String, dynamic> json) {
    return SimulationState(
      ready: json['simulation_ready'] ?? false,
      enabled: json['simulation_enabled'] ?? false,
      speedMultiplier: (json['speed_multiplier'] as num?)?.toDouble() ?? 1.0,
      environmentTime: (json['environment_time'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class PredictiveAlert {
  final String id;
  final String machineId;
  final String message;
  final String severity;
  final DateTime timestamp;
  final Map<String, dynamic> metadata;

  PredictiveAlert({
    required this.id,
    required this.machineId,
    required this.message,
    required this.severity,
    required this.timestamp,
    this.metadata = const {},
  });

  factory PredictiveAlert.fromJson(Map<String, dynamic> json) {
    DateTime ts;
    final rawTs = json['timestamp'];
    if (rawTs == null) {
      ts = DateTime.now();
    } else if (rawTs is num) {
      ts = DateTime.fromMillisecondsSinceEpoch((rawTs * 1000).toInt());
    } else {
      try {
        ts = DateTime.parse(rawTs.toString());
      } catch (_) {
        ts = DateTime.now();
      }
    }
    final payload = json['payload'] is Map
        ? Map<String, dynamic>.from(json['payload'])
        : const <String, dynamic>{};
    final resolvedMachineId =
        (json['machine_id'] ?? payload['machine_id'] ?? json['source'] ?? '')
            .toString();
    final resolvedMessage =
        (json['message'] ??
                json['text'] ??
                json['reason'] ??
                payload['message'] ??
                payload['reason'] ??
                json['event_type'] ??
                '')
            .toString();

    return PredictiveAlert(
      id: json['id']?.toString() ?? json['event_id']?.toString() ?? '',
      machineId: resolvedMachineId,
      message: resolvedMessage,
      severity: json['severity'] ?? 'info',
      timestamp: ts,
      metadata: Map<String, dynamic>.from(json['metadata'] ?? payload),
    );
  }
}
