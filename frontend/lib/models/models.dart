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

class FactoryLayout {
  final List<LayoutNode> nodes;
  final List<LayoutEdge> edges;

  FactoryLayout({required this.nodes, required this.edges});

  Map<String, dynamic> toJson() => {
    'nodes': nodes.map((n) => n.toJson()).toList(),
    'edges': edges.map((e) => e.toJson()).toList(),
  };

  factory FactoryLayout.fromJson(Map<String, dynamic> json) {
    return FactoryLayout(
      nodes: (json['nodes'] as List).map((n) => LayoutNode.fromJson(n)).toList(),
      edges: (json['edges'] as List).map((e) => LayoutEdge.fromJson(e)).toList(),
    );
  }
}

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

  MachineMetrics({
    required this.machineId,
    required this.status,
    required this.healthIndex,
    required this.remainingUsefulLife,
    required this.queueLength,
    required this.productionCount,
    required this.oee,
  });

  factory MachineMetrics.fromJson(Map<String, dynamic> json) {
    return MachineMetrics(
      machineId: json['machine_id'] ?? json['id'] ?? '',
      status: MachineStatus.fromString(json['status'] ?? 'Idle'),
      healthIndex: (json['health_index'] as num?)?.toDouble() ?? 100.0,
      remainingUsefulLife: (json['rul'] as num?)?.toDouble() ?? 500.0,
      queueLength: json['queue_length'] ?? 0,
      productionCount: json['production_count'] ?? 0,
      oee: (json['oee'] as num?)?.toDouble() ?? 0.0,
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
  });

  factory GlobalMetrics.fromJson(Map<String, dynamic> json) {
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
