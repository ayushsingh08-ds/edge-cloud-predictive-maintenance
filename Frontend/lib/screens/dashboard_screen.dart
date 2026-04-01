import 'package:flutter/material.dart';
import 'package:frontend/theme/app_theme.dart';
import 'package:frontend/widgets/digital_twin_panel.dart';
import 'package:frontend/widgets/event_timeline.dart';
import 'package:frontend/widgets/kpi_row.dart';
import 'package:frontend/widgets/telemetry_panel.dart';

import 'package:fl_chart/fl_chart.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Operations Overview',
                  style: Theme.of(context).textTheme.displaySmall,
                ),
                const SizedBox(height: 8),
                Text(
                  'Real-time factory floor synchronization and predictive diagnostics.',
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        color: AppTheme.textMuted,
                      ),
                ),
              ],
            ),
            const Spacer(),
            ElevatedButton.icon(
              onPressed: () {},
              icon: Icon(Icons.download, size: 16),
              label: const Text('Export Data'),
            ),
          ],
        ),
        const SizedBox(height: 32),
        
        // Top Panels Row
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Expanded(flex: 2, child: DigitalTwinPanel()),
            const SizedBox(width: 24),
            const Expanded(flex: 3, child: TelemetryPanel()),
          ],
        ),
        const SizedBox(height: 24),
        
        // KPI Row
        const KpiRow(),
        const SizedBox(height: 24),
        
        // Event Timeline
        const EventTimeline(),
      ],
    );
  }
}
