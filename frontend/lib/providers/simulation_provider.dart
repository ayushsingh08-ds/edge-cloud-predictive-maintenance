import 'dart:async';
import 'dart:convert';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/models.dart';
import '../services/api_service.dart';

class JobParticle {
  final String edgeId;
  final String fromNode;
  final String toNode;
  final DateTime startTime;

  JobParticle({
    required this.edgeId,
    required this.fromNode,
    required this.toNode,
    required this.startTime,
  });
}

class SimulationProvider with ChangeNotifier {
  final Map<String, MachineMetrics> _machineMetrics = {};
  final Map<String, List<double>> _healthHistory = {};
  final Map<String, List<double>> _loadHistory = {};
  final Map<String, List<double>> _tempHistory = {};

  final List<Map<String, dynamic>> _alertsFeed = [];
  final List<Map<String, dynamic>> _eventsFeed = [];
  final List<Map<String, dynamic>> _logsFeed = [];
  final Map<String, List<Offset>> _activeJobs = {}; // Map of edgeId -> List of progress offsets
  final Map<String, Set<String>> _nodeToActiveJobs = {}; // nodeId -> Set of jobIds currently at node
  final List<JobParticle> _activeParticles = []; // For 3D Flow Animation

  List<dynamic> _recentEvents = [];
  List<dynamic> _recentAlerts = [];
  GlobalMetrics? _globalMetrics;
  bool _isSimulating = false;
  double _speedMultiplier = 1.0;
  int _lastSequence = -1;
  final Map<String, int> _nodeQueueSizes = {};
  final Map<String, DateTime> _nodeQueueLastFetch = {};
  final Set<String> _nodeQueueFetchInFlight = <String>{};

  bool _backendConnected = true;
  int _healthFailureStreak = 0;
  static const int _maxTransientHealthFailures = 6;
  static const Duration _connectionGraceWindow = Duration(seconds: 15);
  DateTime _lastSuccessfulBackendSignal = DateTime.fromMillisecondsSinceEpoch(
    0,
  );
  bool _healthCheckInFlight = false;
  String? _lastError;
  String? _currentScenarioId;
  int _unreadAlerts = 0;

  final List<double> _throughputHistory = [];
  final List<double> _cycleTimeHistory = [];
  final List<int> _wipHistory = [];
  List<String> _bottlenecks = [];

  final List<FlSpot> _throughputSpots = [];
  final List<FlSpot> _cycleTimeSpots = [];
  final List<FlSpot> _wipSpots = [];

  Timer? _healthTimer;
  WebSocketChannel? _channel;
  final ApiService _apiService = ApiService();
  bool _isDisposed = false;

  VoidCallback? onLayoutChanged;
  Function(Set<String>)? onRoutingRequest;
  Function(String?)? onRoutingDecision;

  Map<String, MachineMetrics> get machineMetrics => _machineMetrics;
  Map<String, List<double>> get healthHistory => _healthHistory;
  Map<String, List<double>> get loadHistory => _loadHistory;
  Map<String, List<double>> get tempHistory => _tempHistory;
  List<dynamic> get recentEvents => _recentEvents;
  List<dynamic> get recentAlerts => _recentAlerts;
  Map<String, List<Offset>> get activeJobs => _activeJobs;
  
  List<JobParticle> get activeParticles {
    final now = DateTime.now();
    _activeParticles.removeWhere((p) => now.difference(p.startTime).inMilliseconds > 1500);
    return _activeParticles;
  }
  
  Set<String> jobsAtNode(String nodeId) => _nodeToActiveJobs[nodeId] ?? {};
  GlobalMetrics? get globalMetrics => _globalMetrics;
  bool get isSimulating => _isSimulating;
  double get speedMultiplier => _speedMultiplier;
  bool get backendConnected =>
      _backendConnected || _isWsConnected || _hasRecentBackendSignal();
  String? get lastError => _lastError;
  bool get isTelemetryActive => _backendConnected;
  String? get currentScenarioId => _currentScenarioId;

  List<double> get throughputHistory => _throughputHistory;
  List<double> get cycleTimeHistory => _cycleTimeHistory;
  List<int> get wipHistory => _wipHistory;
  List<String> get bottlenecks => _bottlenecks;

  List<Map<String, dynamic>> get alertsFeed => _alertsFeed;
  List<Map<String, dynamic>> get eventsFeed => _eventsFeed;
  List<Map<String, dynamic>> get logsFeed => _logsFeed;
  int get unreadAlerts => _unreadAlerts;

  List<FlSpot> get throughputSpots => _throughputSpots;
  List<FlSpot> get cycleTimeSpots => _cycleTimeSpots;
  List<FlSpot> get wipSpots => _wipSpots;

  bool _isWsConnected = false;
  bool get isWsConnected => _isWsConnected;

  bool _hasRecentBackendSignal() {
    return DateTime.now().difference(_lastSuccessfulBackendSignal) <
        _connectionGraceWindow;
  }

  int queueSizeForNode(String nodeId, {int fallback = 0}) {
    return _nodeQueueSizes[nodeId.toLowerCase()] ?? fallback;
  }

  Future<void> refreshNodeQueueSize(String nodeId) async {
    final key = nodeId.toLowerCase();
    if (_nodeQueueFetchInFlight.contains(key)) {
      return;
    }
    final lastFetch = _nodeQueueLastFetch[key];
    if (lastFetch != null &&
        DateTime.now().difference(lastFetch) <
            const Duration(milliseconds: 900)) {
      return;
    }

    _nodeQueueFetchInFlight.add(key);
    _nodeQueueLastFetch[key] = DateTime.now();
    try {
      final queue = await _apiService.getNodeQueueSize(nodeId);
      if (queue != null && _nodeQueueSizes[key] != queue) {
        _nodeQueueSizes[key] = queue;
        _safeNotifyListeners();
      }
    } finally {
      _nodeQueueFetchInFlight.remove(key);
    }
  }

  void _markBackendAlive() {
    _lastSuccessfulBackendSignal = DateTime.now();
    _healthFailureStreak = 0;
    _backendConnected = true;
  }

  Future<void> toggleSimulation() async {
    final targetState = !_isSimulating;
    final response = await _apiService.toggleSimulation(targetState);
    if (response.success) {
      _isSimulating = targetState;
      if (_isSimulating && !_isWsConnected) {
        _connectWebSocket();
      }
      _appendLog('Simulation ${targetState ? 'STARTED' : 'PAUSED'}.');
      notifyListeners();
    } else {
      _handleError(response);
    }
  }

  Future<void> setSpeedMultiplier(double speed) async {
    final response = await _apiService.setSimulationSpeed(speed);
    if (response.success) {
      _speedMultiplier = speed;
      _appendLog('Simulation speed set to ${speed.toStringAsFixed(1)}x.');
      notifyListeners();
    } else {
      _handleError(response);
    }
  }

  Future<void> initialize() async {
    _startHealthCheck();
    final state = await _apiService.getSimulationState();
    await _syncGlobalMetricsSnapshot(notify: false);
    await _syncMachineMetricsSnapshot(notify: false);
    if (state != null) {
      _isSimulating = state.enabled;
      _speedMultiplier = state.speedMultiplier;
      _markBackendAlive();
      _appendLog(
        'Simulation state synchronized (${_isSimulating ? 'RUNNING' : 'PAUSED'}).',
      );
      if (_isSimulating) {
        _connectWebSocket();
      }
      notifyListeners();
    }
  }

  void _startHealthCheck() {
    _healthTimer?.cancel();
    _healthTimer = Timer.periodic(const Duration(seconds: 4), (timer) async {
      if (_healthCheckInFlight) {
        return;
      }
      _healthCheckInFlight = true;
      try {
        final healthConnected = await _apiService.checkHealth();
        var connected = healthConnected;
        if (!connected) {
          // Fallback probe for transient stalls where only some routes respond.
          connected = await _apiService.getSimulationState() != null;
        }

        if (connected) {
          final wasDisconnected = !_backendConnected;
          _markBackendAlive();
          if (wasDisconnected) {
            _appendLog('Backend reachable.');
            if (_isSimulating && !_isWsConnected) {
              _connectWebSocket();
            }
            notifyListeners();
          }
        } else {
          // Keep UI connected during transient misses.
          if (!_isWsConnected) {
            _healthFailureStreak += 1;
            final hasRecentBackendSignal = _hasRecentBackendSignal();
            if (!hasRecentBackendSignal &&
                _healthFailureStreak >= _maxTransientHealthFailures &&
                _backendConnected) {
              _backendConnected = false;
              _appendLog('Backend sync lost (heartbeat failed).');
              notifyListeners();
            }
          }
        }

        if (connected && _backendConnected) {
          await _syncGlobalMetricsSnapshot();
        }
      } finally {
        _healthCheckInFlight = false;
      }
    });
  }

  Future<void> _syncGlobalMetricsSnapshot({bool notify = true}) async {
    final snapshot = await _apiService.getGlobalMetrics();
    if (snapshot == null) {
      return;
    }
    _markBackendAlive();
    _applyGlobalMetrics(snapshot, notify: notify);
  }

  Future<void> _syncMachineMetricsSnapshot({bool notify = true}) async {
    try {
      final metricsMap = await _apiService.getLatestMetrics();
      if (metricsMap.isNotEmpty) {
        _machineMetrics.addAll(metricsMap);
        if (notify) notifyListeners();
      }
    } catch (e) {
      _lastError = 'Failed to sync machine metrics: $e';
    }
  }

  Future<void> startSimulation() async {
    if (_isSimulating) return;

    final response = await _apiService.toggleSimulation(true);
    if (!response.success) {
      _handleError(response);
      return;
    }

    _isSimulating = true;
    _appendLog('Simulation started.');
    _connectWebSocket();
    notifyListeners();
  }

  Future<void> stopSimulation() async {
    if (!_isSimulating) return;

    final response = await _apiService.toggleSimulation(false);
    if (!response.success) {
      _handleError(response);
      return;
    }

    _isSimulating = false;
    _appendLog('Simulation paused.');
    _channel?.sink.close();
    notifyListeners();
  }

  Future<void> loadScenario(String scenarioId) async {
    _lastError = null;
    notifyListeners();

    final response = await _apiService.loadScenario(scenarioId);
    if (response.success) {
      _currentScenarioId = scenarioId;
      _machineMetrics.clear();
      _healthHistory.clear();
      _loadHistory.clear();
      _tempHistory.clear();
      _throughputHistory.clear();
      _cycleTimeHistory.clear();
      _wipHistory.clear();
      _throughputSpots.clear();
      _cycleTimeSpots.clear();
      _wipSpots.clear();
      _recentAlerts.clear();
      _recentEvents.clear();
      _alertsFeed.clear();
      _eventsFeed.clear();
      _logsFeed.clear();
      _lastSequence = -1;
      _unreadAlerts = 0;

      final data = response.data;
      if (data is Map<String, dynamic>) {
        _isSimulating = data['simulation_enabled'] == true;
      } else {
        _isSimulating = true;
      }

      _appendLog('Scenario loaded: $scenarioId');
      if (_isSimulating) {
        _connectWebSocket();
      }
      if (onLayoutChanged != null) onLayoutChanged!();
      
      await _syncGlobalMetricsSnapshot(notify: false);
      await _syncMachineMetricsSnapshot(notify: false);
      notifyListeners();
    } else {
      _handleError(response);
    }
  }

  Future<Map<String, dynamic>?> runWhatIf(
    Map<String, dynamic> scenario,
    double lookahead,
  ) async {
    final response = await _apiService.runWhatIfScenario(scenario, lookahead);
    if (response.success && response.data != null) {
      _appendLog('What-If branch simulation completed.');
      return response.data as Map<String, dynamic>;
    }
    _handleError(response);
    return null;
  }

  Future<bool> applyOptimizationPolicy(String policy) async {
    final response = await _apiService.applyOptimizationPolicy(policy);
    if (response.success) {
      _appendLog('Optimization applied. Routing policy set to $policy.');
      return true;
    }
    _handleError(response);
    return false;
  }

  Future<void> stepSimulation(double duration) async {
    final response = await _apiService.runSimulationStep(duration);
    if (!response.success) _handleError(response);
  }

  Future<void> setSpeed(double speed) async {
    final response = await _apiService.setSimulationSpeed(speed);
    if (response.success) {
      _speedMultiplier = speed;
      _appendLog('Simulation speed changed to ${speed.toStringAsFixed(1)}x.');
      notifyListeners();
    } else {
      _handleError(response);
    }
  }

  void markAlertsSeen() {
    if (_unreadAlerts == 0) {
      return;
    }
    _unreadAlerts = 0;
    notifyListeners();
  }

  void _handleError(ApiResponse response) {
    _lastError = response.message ?? 'Unknown API Error';
    _appendLog('Error: ${_lastError ?? 'Unknown'}');
    _safeNotifyListeners();
    Future.delayed(const Duration(seconds: 3), () {
      if (_isDisposed) {
        return;
      }
      _lastError = null;
      _safeNotifyListeners();
    });
  }

  void _safeNotifyListeners() {
    if (_isDisposed) {
      return;
    }
    notifyListeners();
  }

  void _connectWebSocket() {
    _channel?.sink.close();
    final wasWsConnected = _isWsConnected;
    _isWsConnected = false;
    if (wasWsConnected) {
      notifyListeners();
    }

    try {
      _channel = _apiService.connectToEvents();
      _channel!.stream.listen(
        (data) {
          final wasDisconnected = !_backendConnected;
          _markBackendAlive();
          if (wasDisconnected) {
            _appendLog('Backend connected via WebSocket.');
            notifyListeners();
          }
          if (!_isWsConnected) {
            _isWsConnected = true;
            notifyListeners();
          }
          _handleWebSocketEvent(data);
        },
        onError: (e) {
          _isWsConnected = false;
          notifyListeners();
        },
        onDone: () {
          _isWsConnected = false;
          notifyListeners();
          if (_isSimulating && _backendConnected) {
            Future.delayed(
              const Duration(seconds: 2),
              () => _connectWebSocket(),
            );
          }
        },
      );
    } catch (e) {
      _isWsConnected = false;
      notifyListeners();
    }
  }

  void _handleWebSocketEvent(dynamic data) {
    // HEAL: If we are receiving events, the backend is 100% connected.
    // This resolves the 'Ghost Connection' where the overlay stays up despite data flow.
    _markBackendAlive();

    Map<String, dynamic>? event;
    try {
      if (data is String) {
        event = jsonDecode(data);
      } else if (data is Map<String, dynamic>) {
        event = data;
      }
      if (event == null) return;

      final eventType = (event['event_type'] ?? '').toString();
      if (eventType == 'MACHINE_METRICS_UPDATE') {
        final payload = event['payload'];
        if (payload is Map) {
          payload.forEach((key, value) {
            if (value is Map) {
              final metrics = MachineMetrics.fromJson(Map<String, dynamic>.from(value));
              _machineMetrics[key.toString().toLowerCase()] = metrics;
            }
          });
          notifyListeners();
        }
        return;
      }

      if (eventType == 'GLOBAL_METRICS') {
        _handleGlobalMetrics(Map<String, dynamic>.from(event['payload'] ?? {}));
        return;
      }

      if (eventType == 'BULK_UPDATE') {
        final payload = event['payload'];
        if (payload is List) {
          for (final item in payload) {
            if (item is Map) {
              _dispatchIncomingEvent(Map<String, dynamic>.from(item));
            }
          }
          notifyListeners();
        }
        return;
      }

      _dispatchIncomingEvent(event);
      notifyListeners();
    } catch (_) {
      // Ignore malformed packets and keep stream alive.
    }
  }

  void _dispatchIncomingEvent(Map<String, dynamic> event) {
    final seq = _readSequence(event);
    if (seq != null && seq < _lastSequence) {
      return;
    }
    if (seq != null) {
      _lastSequence = seq;
    }

    final type = (event['event_type'] ?? '').toString();
    final payload = Map<String, dynamic>.from(event['payload'] ?? {});
    final source = (event['source'] ?? '').toString();
    final timestamp = _eventTimestamp(event);

    if (type == 'ROUTING_REQUEST' && onRoutingRequest != null) {
      final candidates = <String>{};
      final rawCandidates = payload['candidates'];
      if (rawCandidates is List) {
        for (final candidate in rawCandidates) {
          if (candidate is Map) {
            final to = candidate['to_node'];
            final from = candidate['from_node'];
            if (from != null && to != null) {
              candidates.add('${from}_to_${to}');
            }
          }
        }
      }
      if (candidates.isNotEmpty) {
        onRoutingRequest!(candidates);
      }
    }

    if (type == 'ROUTING_DECISION' && onRoutingDecision != null) {
      final from = (payload['from'] ?? payload['from_node'] ?? '')
          .toString()
          .toLowerCase();
      final to = (payload['to'] ?? payload['to_node'] ?? '')
          .toString()
          .toLowerCase();
      if (from.isNotEmpty && to.isNotEmpty) {
        onRoutingDecision!('${from}_to_$to');
      }
    }

    if (type == 'LAYOUT_CHANGED' && onLayoutChanged != null) {
      onLayoutChanged!();
    }

    if (type == 'JOB_TRANSFER') {
      final from = (payload['from_node'] ?? '').toString();
      final to = (payload['to_node'] ?? '').toString();
      final state = (payload['state'] ?? '').toString();
      final jobId = (payload['job_id'] ?? '').toString();
      
      if (state == 'moving' && from.isNotEmpty && to.isNotEmpty) {
        final edgeId = '${from}_to_${to}';
        // Notify UI to start animation on this edge
        if (onRoutingDecision != null) onRoutingDecision!(edgeId);
        _nodeToActiveJobs[from]?.remove(jobId);
        
        // Add particle for 3D Flow Animation
        _activeParticles.add(JobParticle(
          edgeId: edgeId,
          fromNode: from,
          toNode: to,
          startTime: DateTime.now(),
        ));
      } else if (state == 'delivered' && to.isNotEmpty) {
        _nodeToActiveJobs.putIfAbsent(to, () => {}).add(jobId);
        notifyListeners();
      }
    }

    if (type == 'JOB_COMPLETED') {
      final jobId = (payload['job_id'] ?? '').toString();
      final sinkId = (payload['sink_id'] ?? '').toString();
      _nodeToActiveJobs[sinkId]?.remove(jobId);
      notifyListeners();
    }

    if (type == 'JOB_START') {
      final machineId = (payload['machine_id'] ?? '').toString();
      final jobId = (payload['job_id'] ?? '').toString();
      _nodeToActiveJobs.putIfAbsent(machineId, () => {}).add(jobId);
    }

    final machineId = _machineIdForEvent(payload, source);
    if (machineId != null) {
      _updateMachineMetrics(machineId, type, payload);
    }

    final normalized = {
      'seq': seq,
      'event_type': type,
      'source': source,
      'payload': payload,
      'timestamp': timestamp,
      'message': _messageForEvent(type, payload, source),
    };

    if (_isAlertType(type)) {
      _pushLimited(_alertsFeed, normalized, 200);
      _pushLimited(_recentAlerts, normalized, 200);
      _unreadAlerts += 1;
    }

    if (_isEventType(type)) {
      _pushLimited(_eventsFeed, normalized, 400);
      _pushLimited(_recentEvents, normalized, 400);
    }

    if (_isLogType(type)) {
      _pushLimited(_logsFeed, normalized, 400);
    }
  }

  void _handleGlobalMetrics(Map<String, dynamic> payload) {
    _applyGlobalMetrics(GlobalMetrics.fromJson(payload));
  }

  void _applyGlobalMetrics(GlobalMetrics metrics, {bool notify = true}) {
    _globalMetrics = metrics;
    _refreshBottlenecks();

    _throughputHistory.add(_globalMetrics!.throughput);
    if (_throughputHistory.length > 120) _throughputHistory.removeAt(0);

    _cycleTimeHistory.add(_globalMetrics!.avgCycleTime);
    if (_cycleTimeHistory.length > 120) _cycleTimeHistory.removeAt(0);

    _wipHistory.add(_globalMetrics!.wip);
    if (_wipHistory.length > 120) _wipHistory.removeAt(0);

    _appendMetricSpot(_throughputSpots, _globalMetrics!.throughput);
    _appendMetricSpot(_cycleTimeSpots, _globalMetrics!.avgCycleTime);
    _appendMetricSpot(_wipSpots, _globalMetrics!.wip.toDouble());

    if (notify) {
      notifyListeners();
    }
  }

  void _appendMetricSpot(List<FlSpot> target, double value) {
    final now = DateTime.now().millisecondsSinceEpoch / 1000.0;
    target.add(FlSpot(now, value));
    final minTs = now - 60.0;
    target.removeWhere((spot) => spot.x < minTs);
  }

  void _appendLog(String message) {
    final row = {
      'event_type': 'SYSTEM_LOG',
      'message': message,
      'timestamp': DateTime.now().toIso8601String(),
      'source': 'simulation.provider',
      'payload': <String, dynamic>{},
    };
    _pushLimited(_logsFeed, row, 400);
  }

  void _pushLimited(List<dynamic> list, dynamic item, int limit) {
    list.add(item);
    if (list.length > limit) {
      list.removeRange(0, list.length - limit);
    }
  }

  int? _readSequence(Map<String, dynamic> event) {
    final raw = event['seq'] ?? event['sequence'];
    if (raw is int) return raw;
    if (raw is num) return raw.toInt();
    if (raw is String) return int.tryParse(raw);
    return null;
  }

  String _eventTimestamp(Map<String, dynamic> event) {
    final raw = event['timestamp'];
    if (raw == null) return DateTime.now().toIso8601String();
    if (raw is String) return raw;
    if (raw is num) {
      return DateTime.fromMillisecondsSinceEpoch(
        (raw * 1000).toInt(),
      ).toIso8601String();
    }
    return DateTime.now().toIso8601String();
  }

  bool _isAlertType(String type) {
    return type == 'MAINTENANCE_TRIGGER' ||
        type == 'MACHINE_FAILURE' ||
        type == 'MAINTENANCE_STATE';
  }

  bool _isEventType(String type) {
    return type == 'ROUTING_DECISION' ||
        type == 'JOB_FINISH' ||
        type == 'JOB_COMPLETED';
  }

  bool _isLogType(String type) {
    return type == 'GLOBAL_METRICS' ||
        type == 'LAYOUT_CHANGED' ||
        type == 'SIMULATION_TOGGLED' ||
        type == 'ROUTING_DECISION';
  }

  String _messageForEvent(
    String type,
    Map<String, dynamic> payload,
    String source,
  ) {
    if (type == 'ROUTING_DECISION') {
      var from =
          (payload['from'] ?? payload['from_node'] ?? payload['divider_id'])
              ?.toString() ??
          '';
      if (from.isEmpty) {
        if (source.startsWith('divider.')) {
          from = source.split('.').last;
        } else if (source == 'routing.engine') {
          from = 'router';
        } else {
          from = 'unknown';
        }
      }
      final to = (payload['to'] ?? payload['to_node'] ?? 'unknown').toString();
      final policy = payload['routing_policy'] ?? payload['policy'] ?? 'n/a';
      return 'Route $from -> $to ($policy)';
    }
    if (type == 'MACHINE_FAILURE') {
      return 'Machine failure detected at ${payload['machine_id'] ?? source}';
    }
    if (type == 'MAINTENANCE_TRIGGER' || type == 'MAINTENANCE_STATE') {
      return payload['message']?.toString() ??
          'Maintenance event for ${payload['machine_id'] ?? source}';
    }
    if (type == 'JOB_FINISH' || type == 'JOB_COMPLETED') {
      return 'Job ${payload['job_id'] ?? ''} completed.';
    }
    return type;
  }

  String? _machineIdForEvent(Map<String, dynamic> payload, String source) {
    final machineId = payload['machine_id'];
    if (machineId is String && machineId.isNotEmpty) {
      return machineId.toLowerCase();
    }
    if (source.startsWith('machine.')) {
      return source.split('.').last.toLowerCase();
    }
    return null;
  }

  void _updateMachineMetrics(
    String machineId,
    String eventType,
    Map<String, dynamic> payload,
  ) {
    var metrics =
        _machineMetrics[machineId] ??
        MachineMetrics(
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
        final innerPayload = payload['metrics'] is Map
            ? Map<String, dynamic>.from(payload['metrics'])
            : payload;
        metrics = metrics.copyWith(
          healthIndex: _normalizeHealth(
            _parseNum(innerPayload, [
              'health',
              'health_index',
              'condition',
            ], fallback: metrics.healthIndex),
          ),
          oee: _parseNum(innerPayload, [
            'oee',
            'efficiency',
            'oee_score',
          ], fallback: metrics.oee),
          load: _parseNum(innerPayload, [
            'load',
            'utilization',
            'load_factor',
          ], fallback: metrics.load),
          temperature: _parseNum(innerPayload, [
            'temperature',
            'temp',
            'thermal',
          ], fallback: metrics.temperature),
          vibration: _parseNum(innerPayload, [
            'vibration',
            'vib',
            'frequency',
          ], fallback: metrics.vibration),
          utilization: _parseNum(innerPayload, [
            'utilization',
            'load',
            'busy_factor',
          ], fallback: metrics.utilization),
        );
        break;
      case 'MACHINE_FAILURE':
        metrics = metrics.copyWith(status: MachineStatus.failed);
        break;
      case 'MACHINE_REPAIR':
        metrics = metrics.copyWith(status: MachineStatus.idle);
        break;
      case 'HEALTH_UPDATE':
        metrics = metrics.copyWith(
          healthIndex: _normalizeHealth(
            _parseNum(payload, [
              'health',
              'health_index',
            ], fallback: metrics.healthIndex),
          ),
          queueLength: _parseNum(payload, [
            'queue_length',
          ], fallback: metrics.queueLength.toDouble()).round(),
          utilization: _parseNum(payload, [
            'utilization',
          ], fallback: metrics.utilization),
          shapImportance: Map<String, double>.from(
            (payload['shap_importance'] as Map? ?? {}).map(
              (k, v) => MapEntry(k.toString(), (v as num).toDouble()),
            ),
          ),
          confidenceScore: _parseNum(payload, ['confidence_score'], fallback: metrics.confidenceScore),
        );
        break;
      case 'RUL_PREDICTION':
        metrics = metrics.copyWith(
          remainingUsefulLife: _parseNum(payload, [
            'remaining_useful_life',
            'rul',
            'remaining_life',
          ], fallback: metrics.remainingUsefulLife),
          shapImportance: Map<String, double>.from(
            (payload['shap_importance'] as Map? ?? {}).map(
              (k, v) => MapEntry(k.toString(), (v as num).toDouble()),
            ),
          ),
          confidenceScore: _parseNum(payload, ['confidence_score'], fallback: metrics.confidenceScore),
        );
        break;
      case 'JOB_START':
        metrics = metrics.copyWith(status: MachineStatus.busy);
        break;
      case 'JOB_FINISH':
      case 'JOB_COMPLETED':
        metrics = metrics.copyWith(
          status: MachineStatus.idle,
          productionCount: metrics.productionCount + 1,
        );
        break;
    }

    _machineMetrics[machineId] = metrics;

    _updateHistory(_healthHistory, machineId, metrics.healthIndex);
    _updateHistory(_loadHistory, machineId, metrics.load);
    _updateHistory(_tempHistory, machineId, metrics.temperature);

    _refreshBottlenecks();
  }

  void _refreshBottlenecks() {
    final backendBottlenecks =
        _globalMetrics?.bottleneckNodes ?? const <String>[];
    if (backendBottlenecks.isNotEmpty) {
      _bottlenecks = backendBottlenecks;
      return;
    }

    _bottlenecks = _machineMetrics.values
        .where((m) => m.queueLength > 5 || m.healthIndex < 40.0)
        .map((m) => m.machineId)
        .toList();
  }

  double _normalizeHealth(double value) {
    if (value <= 1.0) {
      return (value * 100.0).clamp(0.0, 100.0);
    }
    return value.clamp(0.0, 100.0);
  }

  double _parseNum(
    dynamic payload,
    List<String> aliases, {
    double fallback = 0.0,
  }) {
    if (payload == null || payload is! Map) return fallback;

    for (final alias in aliases) {
      final val = payload[alias];
      if (val == null) continue;

      if (val is num) return val.toDouble();
      if (val is String) return double.tryParse(val) ?? fallback;
      if (val is Map && val.containsKey('value')) {
        final innerVal = val['value'];
        if (innerVal is num) return innerVal.toDouble();
        if (innerVal is String) return double.tryParse(innerVal) ?? fallback;
      }
    }
    return fallback;
  }

  void _updateHistory(
    Map<String, List<double>> buffer,
    String id,
    double value,
  ) {
    buffer.putIfAbsent(id, () => []);
    buffer[id]!.add(value);
    if (buffer[id]!.length > 60) {
      buffer[id]!.removeAt(0);
    }
  }

  @override
  void dispose() {
    _isDisposed = true;
    _healthTimer?.cancel();
    _channel?.sink.close();
    super.dispose();
  }
}
