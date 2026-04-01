import 'dart:convert';
import 'dart:developer';
import 'package:http/http.dart' as http;

class ApiService {
  static const String _baseUrl = 'http://localhost:8000/api';

  // Reusable GET helper
  static Future<dynamic> _get(String endpoint) async {
    try {
      final response = await http.get(Uri.parse('$_baseUrl$endpoint'));
      return _handleResponse(response);
    } catch (e) {
      log('GET Error at $endpoint: $e');
      rethrow;
    }
  }

  // Reusable POST helper
  static Future<dynamic> _post(String endpoint, Map<String, dynamic> body) async {
    try {
      final response = await http.post(
        Uri.parse('$_baseUrl$endpoint'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      );
      return _handleResponse(response);
    } catch (e) {
      log('POST Error at $endpoint: $e');
      rethrow;
    }
  }

  // Response handler
  static dynamic _handleResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body);
    } else {
      throw Exception('API Error: ${response.statusCode} - ${response.body}');
    }
  }

  // --- Machine Endpoints ---

  static Future<List<dynamic>> getMachines() async {
    return await _get('/machines');
  }

  static Future<Map<String, dynamic>> getMachineHealth(String id) async {
    return await _get('/machines/$id/health');
  }

  // --- Job & Queue Endpoints ---

  static Future<List<dynamic>> getQueue() async {
    return await _get('/queue');
  }

  static Future<Map<String, dynamic>> getJobsStatistics() async {
    return await _get('/jobs/statistics');
  }

  // --- Anomaly Endpoints ---

  static Future<List<dynamic>> getAnomalies() async {
    return await _get('/anomalies');
  }

  // --- Simulation Endpoints ---

  static Future<Map<String, dynamic>> runSimulation(Map<String, dynamic> params) async {
    return await _post('/simulation/run', params);
  }

  static Future<List<dynamic>> getSimulationHistory() async {
    return await _get('/simulation/history');
  }

  // --- RL Training Endpoints ---

  static Future<Map<String, dynamic>> startRLTraining(Map<String, dynamic> params) async {
    return await _post('/rl/train', params);
  }

  static Future<Map<String, dynamic>> getTrainingStatus(String id) async {
    return await _get('/rl/training/$id/status');
  }

  // --- Metrics & Forecast Endpoints ---

  static Future<Map<String, dynamic>> getCurrentMetrics() async {
    return await _get('/metrics/current');
  }

  static Future<List<dynamic>> getMetricsHistory() async {
    return await _get('/metrics/history');
  }

  static Future<Map<String, dynamic>> getRULForecast() async {
    return await _get('/forecast/rul');
  }

  // --- System Status ---

  static Future<Map<String, dynamic>> getSystemStatus() async {
    return await _get('/system/status');
  }
}
