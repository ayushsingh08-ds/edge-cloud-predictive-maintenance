import 'dart:async';
import 'dart:convert';
import 'dart:developer';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;

enum WebSocketEventType {
  machine,
  simulation,
  anomaly,
  jobRouting,
  kpiUpdate,
  metricsUpdate,
  unknown
}

class WebSocketEvent {
  final WebSocketEventType type;
  final dynamic data;

  WebSocketEvent({required this.type, required this.data});
}

class WebSocketService {
  static const String _wsUrl = 'ws://localhost:8000/ws/events';
  
  WebSocketChannel? _channel;
  final StreamController<WebSocketEvent> _eventController = StreamController<WebSocketEvent>.broadcast();
  
  bool _isConnected = false;
  Timer? _reconnectTimer;

  // Stream for widgets to listen to
  Stream<WebSocketEvent> get eventStream => _eventController.stream;
  bool get isConnected => _isConnected;

  void connect() {
    try {
      log('WebSocket: Connecting to $_wsUrl...');
      _channel = WebSocketChannel.connect(Uri.parse(_wsUrl));
      
      _channel!.stream.listen(
        (message) {
          _isConnected = true;
          _handleMessage(message);
        },
        onDone: () {
          log('WebSocket: Connection closed.');
          _isConnected = false;
          _scheduleReconnect();
        },
        onError: (error) {
          log('WebSocket: Error: $error');
          _isConnected = false;
          _scheduleReconnect();
        },
      );
    } catch (e) {
      log('WebSocket: Connection failed: $e');
      _scheduleReconnect();
    }
  }

  void _handleMessage(dynamic message) {
    try {
      final Map<String, dynamic> decoded = jsonDecode(message);
      final String typeStr = decoded['type'] ?? 'unknown';
      final dynamic data = decoded['data'];

      WebSocketEventType type;
      switch (typeStr) {
        case 'machine':
          type = WebSocketEventType.machine;
          break;
        case 'simulation':
          type = WebSocketEventType.simulation;
          break;
        case 'anomaly':
          type = WebSocketEventType.anomaly;
          break;
        case 'job_routing':
          type = WebSocketEventType.jobRouting;
          break;
        case 'kpi_update':
          type = WebSocketEventType.kpiUpdate;
          break;
        case 'metrics_update':
          type = WebSocketEventType.metricsUpdate;
          break;
        default:
          type = WebSocketEventType.unknown;
      }

      _eventController.add(WebSocketEvent(type: type, data: data));
    } catch (e) {
      log('WebSocket: Message parsing error: $e');
    }
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), () {
      log('WebSocket: Attempting to reconnect...');
      connect();
    });
  }

  void sendMessage(Map<String, dynamic> message) {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(jsonEncode(message));
    } else {
      log('WebSocket: Cannot send message, not connected.');
    }
  }

  void disconnect() {
    _reconnectTimer?.cancel();
    _channel?.sink.close(status.goingAway);
    _isConnected = false;
  }

  void dispose() {
    disconnect();
    _eventController.close();
  }
}
