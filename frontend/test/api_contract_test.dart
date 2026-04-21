import 'package:flutter_test/flutter_test.dart';

import 'package:smart_factory_layout_editor/models/models.dart';
import 'package:smart_factory_layout_editor/services/api_service.dart';

void main() {
  group('PredictiveAlert parsing', () {
    test('reads backend event payload fields', () {
      final alert = PredictiveAlert.fromJson({
        'event_id': 'evt-123',
        'event_type': 'MAINTENANCE_TRIGGER',
        'source': 'ml.prediction_service',
        'timestamp': '2026-04-05T10:15:30Z',
        'severity': 'critical',
        'payload': {
          'machine_id': 'machine-7',
          'reason': 'predicted_risk_threshold',
          'message': 'Maintenance recommended',
        },
      });

      expect(alert.id, 'evt-123');
      expect(alert.machineId, 'machine-7');
      expect(alert.message, 'Maintenance recommended');
      expect(alert.severity, 'critical');
      expect(alert.metadata['reason'], 'predicted_risk_threshold');
    });

    test('falls back to event type when message is absent', () {
      final alert = PredictiveAlert.fromJson({
        'event_id': 'evt-456',
        'event_type': 'ROUTING_DECISION',
        'source': 'routing.engine',
        'timestamp': 1712311230,
        'payload': {'machine_id': 'machine-3'},
      });

      expect(alert.id, 'evt-456');
      expect(alert.machineId, 'machine-3');
      expect(alert.message, 'ROUTING_DECISION');
      expect(alert.severity, 'info');
    });
  });

  group('GlobalMetrics parsing', () {
    test('maps backend metric aliases into the Flutter model', () {
      final metrics = GlobalMetrics.fromJson({
        'environment_time': 42.5,
        'machine_count': 3,
        'oee': 0.67,
        'availability': 0.8,
        'performance': 0.9,
        'quality': 0.95,
        'wip': 12,
        'completed_jobs': 21,
        'simulation_enabled': true,
        'throughput_hr': 128.4,
        'cycle_time_s': 4.2,
        'lead_time_m': 1.7,
        'bottlenecks': 2,
        'bottleneck_nodes': ['machine-1', 'machine-2'],
        'avg_util': 0.55,
      });

      expect(metrics.environmentTime, 42.5);
      expect(metrics.machineCount, 3);
      expect(metrics.oee, 0.67);
      expect(metrics.throughput, 128.4);
      expect(metrics.avgCycleTime, 4.2);
      expect(metrics.leadTime, 1.7);
      expect(metrics.bottlenecks, 2);
      expect(metrics.bottleneckNodes, ['machine-1', 'machine-2']);
      expect(metrics.avgUtilization, 0.55);
    });
  });

  group('ApiService websocket contract', () {
    test('builds websocket uri from configured base url', () {
      final httpService = ApiService(baseUrl: 'http://127.0.0.1:8010');
      final httpsService = ApiService(
        baseUrl: 'https://factory.example.com/api',
      );

      expect(
        httpService.eventsWebSocketUri().toString(),
        'ws://127.0.0.1:8010/ws/events',
      );
      expect(
        httpsService.eventsWebSocketUri().toString(),
        'wss://factory.example.com/ws/events',
      );
    });
  });
}
