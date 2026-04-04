import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class SimulationProvider with ChangeNotifier {
  final Map<String, MachineMetrics> _machineMetrics = {};
  GlobalMetrics? _globalMetrics;
  bool _isSimulating = false;
  double _speedMultiplier = 1.0;
  
  Timer? _stepTimer;
  Timer? _metricsTimer;
  WebSocketChannel? _channel;
  final ApiService _apiService = ApiService();

  Map<String, MachineMetrics> get machineMetrics => _machineMetrics;
  GlobalMetrics? get globalMetrics => _globalMetrics;
  bool get isSimulating => _isSimulating;
  double get speedMultiplier => _speedMultiplier;

  Future<void> initialize() async {
    final state = await _apiService.getSimulationState();
    if (state != null) {
      _isSimulating = state.enabled;
      _speedMultiplier = state.speedMultiplier;
      if (_isSimulating) {
        startSimulation();
      }
      notifyListeners();
    }
  }

  void startSimulation() async {
    if (_isSimulating) return;
    
    final success = await _apiService.toggleSimulation(true);
    if (!success) return;

    _isSimulating = true;
    _startHeartbeat();
    _connectWebSocket();
    notifyListeners();
  }

  void stopSimulation() async {
    if (!_isSimulating) return;
    
    await _apiService.toggleSimulation(false);
    _isSimulating = false;
    _stopHeartbeat();
    _channel?.sink.close();
    notifyListeners();
  }

  void setSpeed(double speed) async {
    final success = await _apiService.setSimulationSpeed(speed);
    if (success) {
      _speedMultiplier = speed;
      notifyListeners();
    }
  }

  void _startHeartbeat() {
    _stepTimer?.cancel();
    _metricsTimer?.cancel();

    // Pulse advanced simulation time
    _stepTimer = Timer.periodic(const Duration(milliseconds: 500), (timer) async {
      if (!_isSimulating) return;
      await _apiService.runSimulationStep(0.5);
    });

    // Pulse global metrics
    _metricsTimer = Timer.periodic(const Duration(seconds: 1), (timer) async {
      _globalMetrics = await _apiService.getGlobalMetrics();
      notifyListeners();
    });
  }

  void _stopHeartbeat() {
    _stepTimer?.cancel();
    _metricsTimer?.cancel();
  }

  void _connectWebSocket() {
    _channel?.sink.close();
    try {
      _channel = _apiService.connectToEvents();
      _channel!.stream.listen(_handleWebSocketEvent);
    } catch (e) {
      debugPrint('WebSocket connection failed: $e');
    }
  }

  void _handleWebSocketEvent(dynamic data) {
    try {
      final event = jsonDecode(data);
      final eventType = event['event_type'];
      final source = event['source'] as String;
      final payload = event['payload'];

      if (source.startsWith('machine.')) {
        final machineId = source.split('.').last;
        _updateMachineMetrics(machineId, eventType, payload);
      }
    } catch (e) {
      debugPrint('Error parsing WebSocket event: $e');
    }
  }

  void _updateMachineMetrics(String machineId, String eventType, dynamic payload) {
    var metrics = _machineMetrics[machineId] ?? MachineMetrics(
      machineId: machineId,
      status: MachineStatus.idle,
      healthIndex: 100.0,
      remainingUsefulLife: 500.0,
      queueLength: 0,
      productionCount: 0,
      oee: 0.0,
    );

    switch (eventType) {
      case 'SENSOR_DATA':
        metrics = metrics.copyWith(
          healthIndex: (payload['health'] as num?)?.toDouble() ?? metrics.healthIndex,
          oee: (payload['oee'] as num?)?.toDouble() ?? metrics.oee,
        );
        break;
      case 'MACHINE_FAILURE':
        metrics = metrics.copyWith(status: MachineStatus.failed);
        break;
      case 'MACHINE_REPAIR':
        metrics = metrics.copyWith(status: MachineStatus.idle);
        break;
      case 'HEALTH_UPDATE':
        metrics = metrics.copyWith(healthIndex: (payload['health'] as num?)?.toDouble() ?? metrics.healthIndex);
        break;
      case 'RUL_PREDICTION':
        metrics = metrics.copyWith(remainingUsefulLife: (payload['rul'] as num?)?.toDouble() ?? metrics.remainingUsefulLife);
        break;
    }

    _machineMetrics[machineId] = metrics;
    notifyListeners();
  }

  @override
  void dispose() {
    _stopHeartbeat();
    _channel?.sink.close();
    super.dispose();
  }
}

// Adding copyWith to MachineMetrics for easier updates
extension MachineMetricsExtension on MachineMetrics {
  MachineMetrics copyWith({
    String? machineId,
    MachineStatus? status,
    double? healthIndex,
    double? remainingUsefulLife,
    int? queueLength,
    int? productionCount,
    double? oee,
  }) {
    return MachineMetrics(
      machineId: machineId ?? this.machineId,
      status: status ?? this.status,
      healthIndex: healthIndex ?? this.healthIndex,
      remainingUsefulLife: remainingUsefulLife ?? this.remainingUsefulLife,
      queueLength: queueLength ?? this.queueLength,
      productionCount: productionCount ?? this.productionCount,
      oee: oee ?? this.oee,
    );
  }
}
