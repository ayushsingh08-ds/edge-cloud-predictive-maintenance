import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/models.dart';

class ApiService {
  final String baseUrl;
  final String wsUrl;

  ApiService({
    this.baseUrl = 'http://127.0.0.1:8001',
    this.wsUrl = 'ws://127.0.0.1:8001/ws/events',
  });

  // Health & Catalog
  Future<Map<String, dynamic>?> getHealth() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/health'));
      if (response.statusCode == 200) return jsonDecode(response.body);
      return null;
    } catch (e) {
      return null;
    }
  }

  Future<List<Map<String, dynamic>>?> getCatalog() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/catalog/components'));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<Map<String, dynamic>>.from(data['components'] ?? []);
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  // Granular Layout Sync
  Future<bool> addNode(LayoutNode node) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/layout/node/add'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(node.toJson()),
      );
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<bool> updateNode(LayoutNode node) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/layout/node/update'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(node.toJson()),
      );
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<bool> deleteNode(String nodeId) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/layout/node/delete'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'id': nodeId}),
      );
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<bool> addEdge(LayoutEdge edge) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/layout/edge/add'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(edge.toJson()),
      );
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<bool> deleteEdge(String fromNode, String toNode) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/layout/edge/delete'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'from_node': fromNode, 'to_node': toNode}),
      );
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
  Future<FactoryLayout?> loadLayout() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/layout/current'));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return FactoryLayout.fromJson(data['graph'] ?? data);
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  // Simulation Controls
  Future<SimulationState?> getSimulationState() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/simulation/state'));
      if (response.statusCode == 200) {
        return SimulationState.fromJson(jsonDecode(response.body));
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  Future<bool> toggleSimulation(bool enabled) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/simulation/toggle'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'enabled': enabled}),
      );
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<bool> setSimulationSpeed(double speed) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/simulation/speed'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'speed_multiplier': speed}),
      );
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<Map<String, dynamic>?> runSimulationStep(double duration) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/simulation/run?duration=$duration'),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
      return null;
    } catch (e) {
      return null;
    }
  }

  // Metrics & Alerts
  Future<GlobalMetrics?> getGlobalMetrics() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/metrics/global'));
      if (response.statusCode == 200) {
        return GlobalMetrics.fromJson(jsonDecode(response.body));
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  Future<List<dynamic>> getRecentAlerts({int limit = 20}) async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/alerts/recent?limit=$limit'));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['alerts'] ?? [];
      }
      return [];
    } catch (e) {
      return [];
    }
  }

  WebSocketChannel connectToEvents() {
    return WebSocketChannel.connect(Uri.parse(wsUrl));
  }
}
