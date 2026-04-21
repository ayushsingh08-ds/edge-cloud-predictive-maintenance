import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/models.dart';

class ApiService {
  final String baseUrl;

  ApiService({this.baseUrl = 'http://127.0.0.1:8005'});

  Future<ApiResponse> _wrap(Future<http.Response> request) async {
    try {
      final response = await request;
      final data = jsonDecode(response.body);
      return ApiResponse(
        success: response.statusCode >= 200 && response.statusCode < 300,
        statusCode: response.statusCode,
        data: data,
        message: data is Map ? data['detail'] ?? data['message'] : null,
      );
    } catch (e) {
      return ApiResponse(success: false, message: e.toString());
    }
  }

  // ─── Layout ────────────────────────────────────────────────────────────────

  Future<LayoutGraph?> getLayout() async {
    final response = await _wrap(
      http.get(Uri.parse('$baseUrl/layout/current')),
    );
    if (response.success && response.data != null) {
      final graphData = response.data['graph'];
      if (graphData is Map<String, dynamic>) {
        return LayoutGraph.fromJson(graphData);
      }
    }
    return null;
  }

  Future<LayoutGraph?> loadLayout() => getLayout();

  Future<int?> getNodeQueueSize(String nodeId) async {
    final response = await _wrap(http.get(Uri.parse('$baseUrl/nodes/$nodeId')));
    if (!response.success || response.data == null) {
      return null;
    }

    final raw = response.data['queue_size'];
    if (raw is int) return raw;
    if (raw is num) return raw.toInt();
    if (raw is String) return int.tryParse(raw);
    return null;
  }

  Future<ApiResponse> updateLayout(LayoutGraph graph) => _wrap(
    http.post(
      Uri.parse('$baseUrl/layout'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(graph.toJson()),
    ),
  );

  Future<List<dynamic>?> getCatalog() async {
    final response = await _wrap(
      http.get(Uri.parse('$baseUrl/catalog/components')),
    );
    if (response.success && response.data != null) {
      return response.data['components'] as List<dynamic>;
    }
    return null;
  }

  // ─── Node CRUD (matches backend /layout/node/add etc.) ────────────────────

  Future<ApiResponse> addNode(LayoutNode node) => _wrap(
    http.post(
      Uri.parse('$baseUrl/layout/node/add'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(node.toJson()),
    ),
  );

  Future<ApiResponse> updateNode(LayoutNode node) => _wrap(
    http.post(
      Uri.parse('$baseUrl/layout/node/update'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'node_id': node.id,
        'patch': {
          'position': {'x': node.position.x, 'y': node.position.y},
          'properties': node.properties,
        },
      }),
    ),
  );

  Future<ApiResponse> deleteNode(String nodeId) => _wrap(
    http.post(
      Uri.parse('$baseUrl/layout/node/delete'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'node_id': nodeId}),
    ),
  );

  // ─── Edge CRUD ─────────────────────────────────────────────────────────────

  Future<ApiResponse> addEdge(LayoutEdge edge) => _wrap(
    http.post(
      Uri.parse('$baseUrl/layout/edge/add'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(edge.toJson()),
    ),
  );

  Future<ApiResponse> deleteEdge(String fromNode, String toNode) => _wrap(
    http.post(
      Uri.parse('$baseUrl/layout/edge/delete'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'from_node': fromNode, 'to_node': toNode}),
    ),
  );

  // ─── Simulation ────────────────────────────────────────────────────────────

  Future<SimulationState?> getSimulationState() async {
    final response = await _wrap(
      http.get(Uri.parse('$baseUrl/simulation/state')),
    );
    if (response.success && response.data != null) {
      return SimulationState.fromJson(response.data);
    }
    return null;
  }

  Future<ApiResponse> setSimulationState(bool enabled) => _wrap(
    http.post(
      Uri.parse('$baseUrl/simulation/toggle'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'enabled': enabled}),
    ),
  );

  Future<ApiResponse> setSpeed(double speed) => _wrap(
    http.post(
      Uri.parse('$baseUrl/simulation/speed'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'speed_multiplier': speed}),
    ),
  );

  // ─── Metrics ───────────────────────────────────────────────────────────────

  Future<Map<String, MachineMetrics>> getLatestMetrics() async {
    final response = await _wrap(
      http.get(Uri.parse('$baseUrl/metrics/machines')),
    );
    if (response.success && response.data is Map) {
      final Map<String, dynamic> raw = response.data;
      return raw.map(
        (key, value) => MapEntry(key, MachineMetrics.fromJson(value)),
      );
    }
    return {};
  }

  Future<GlobalMetrics?> getGlobalMetrics() async {
    final response = await _wrap(
      http.get(Uri.parse('$baseUrl/metrics/global')),
    );
    if (response.success && response.data != null) {
      return GlobalMetrics.fromJson(response.data);
    }
    return null;
  }

  Future<List<PredictiveAlert>> getAlerts() async {
    final response = await _wrap(http.get(Uri.parse('$baseUrl/alerts/recent')));
    if (response.success &&
        response.data != null &&
        response.data['alerts'] is List) {
      return (response.data['alerts'] as List)
          .map((e) => PredictiveAlert.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<List<dynamic>> getRecentAlerts({int limit = 100}) async {
    final alerts = await getAlerts();
    return alerts
        .map(
          (a) => {
            'severity': a.severity,
            'message': a.message,
            'timestamp': a.timestamp.toIso8601String(),
            'machine_id': a.machineId,
          },
        )
        .toList();
  }

  Future<List<dynamic>> getRecentEvents({int limit = 200}) async {
    final response = await _wrap(
      http.get(Uri.parse('$baseUrl/events/recent?limit=$limit')),
    );
    if (response.success &&
        response.data != null &&
        response.data['events'] != null) {
      return response.data['events'] as List<dynamic>;
    }
    return [];
  }

  Future<bool> checkHealth() async {
    Future<bool> probe(String path) async {
      try {
        final response = await http
            .get(Uri.parse('$baseUrl$path'))
            .timeout(const Duration(seconds: 2));
        return response.statusCode >= 200 && response.statusCode < 300;
      } catch (_) {
        return false;
      }
    }

    final results = await Future.wait([
      probe('/health'),
      probe('/simulation/state'),
      probe('/layout/current'),
      probe('/events/recent?limit=1'),
    ]);
    return results.any((ok) => ok);
  }

  Future<ApiResponse> toggleSimulation(bool enabled) =>
      setSimulationState(enabled);

  Future<ApiResponse> runSimulationStep(double duration) =>
      _wrap(http.post(Uri.parse('$baseUrl/simulation/run?duration=$duration')));

  Future<ApiResponse> setSimulationSpeed(double speed) => setSpeed(speed);

  // ─── Validation & Scenarios ────────────────────────────────────────────────

  Future<ApiResponse> validateLayout([LayoutGraph? graph]) async {
    final payload = graph?.toJson() ?? (await getLayout())?.toJson();
    if (payload == null) {
      return ApiResponse(
        success: false,
        message: 'No layout available to validate',
      );
    }

    return _wrap(
      http.post(
        Uri.parse('$baseUrl/layout/validate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      ),
    );
  }

  Future<ApiResponse> runWhatIfScenario(
    Map<String, dynamic> scenario,
    double lookahead,
  ) => _wrap(
    http.post(
      Uri.parse('$baseUrl/simulation/what_if'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'scenario': scenario, 'lookahead': lookahead}),
    ),
  );

  Future<ApiResponse> loadScenario(String scenarioId) => _wrap(
    http.post(
      Uri.parse('$baseUrl/scenarios/load'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'scenario_id': scenarioId}),
    ),
  );

  Future<List<dynamic>> listScenarios() async {
    final response = await _wrap(http.get(Uri.parse('$baseUrl/scenarios')));
    if (response.success && response.data != null) {
      return response.data['scenarios'] as List<dynamic>? ?? [];
    }
    return [];
  }

  Future<Map<String, dynamic>?> getRoutingPolicy() async {
    final response = await _wrap(
      http.get(Uri.parse('$baseUrl/routing/policy')),
    );
    if (response.success && response.data != null) {
      return Map<String, dynamic>.from(response.data);
    }
    return null;
  }

  Future<ApiResponse> setRoutingPolicy(String policy) => _wrap(
    http.post(
      Uri.parse('$baseUrl/routing/policy'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'policy': policy}),
    ),
  );

  Future<ApiResponse> patchRoutingPolicy(String policy) => _wrap(
    http.patch(
      Uri.parse('$baseUrl/routing/policy'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'policy': policy}),
    ),
  );

  Future<ApiResponse> applyOptimizationPolicy(String policy) async {
    final normalizedPolicy = _normalizeRoutingPolicy(policy);
    final patched = await patchRoutingPolicy(normalizedPolicy);
    if (patched.success) {
      return patched;
    }
    return setRoutingPolicy(normalizedPolicy);
  }

  String _normalizeRoutingPolicy(String policy) {
    final raw = policy
        .trim()
        .toLowerCase()
        .replaceAll('-', '_')
        .replaceAll(' ', '_');
    const aliasMap = {
      'pdm_priority': 'weighted_cost',
      'shortest_queue': 'least_loaded',
      'balanced': 'round_robin',
    };
    return aliasMap[raw] ?? raw;
  }

  // ─── WebSocket ────────────────────────────────────────────────────────────

  Uri eventsWebSocketUri() {
    final httpUri = Uri.parse(baseUrl);
    final scheme = httpUri.scheme == 'https' ? 'wss' : 'ws';
    return httpUri.replace(scheme: scheme, path: '/ws/events');
  }

  WebSocketChannel connectToEvents() {
    return WebSocketChannel.connect(eventsWebSocketUri());
  }
}

class ApiResponse {
  final bool success;
  final int? statusCode;
  final String? message;
  final dynamic data;

  ApiResponse({
    required this.success,
    this.statusCode,
    this.message,
    this.data,
  });
}
