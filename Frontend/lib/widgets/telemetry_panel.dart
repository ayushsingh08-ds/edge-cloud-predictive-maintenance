import 'package:flutter/material.dart';
import 'package:frontend/theme/app_theme.dart';


class TelemetryPanel extends StatelessWidget {
  const TelemetryPanel({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 440,
      decoration: AppTheme.clayDecoration(),
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Live Telemetry',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              Icon(Icons.monitor, size: 18, color: AppTheme.sageGreen),
            ],
          ),
          const SizedBox(height: 20),
          Expanded(
            child: SingleChildScrollView(
              child: Column(
                children: [
                  _TelemetryMetric(
                    label: 'Temperature',
                    value: '72°C',
                    progress: 0.72,
                    unit: 'Peak 84°C',
                    icon: Icons.thermostat,
                  ),
                  _TelemetryMetric(
                    label: 'Vibration',
                    value: '0.42 mm/s',
                    progress: 0.42,
                    unit: 'RMS',
                    icon: Icons.waves,
                  ),
                  _TelemetryMetric(
                    label: 'Pressure',
                    value: '4.2 Bar',
                    progress: 0.65,
                    unit: 'Nominal 4.0',
                    icon: Icons.speed,
                  ),
                  _TelemetryMetric(
                    label: 'Utilization',
                    value: '91.4%',
                    progress: 0.91,
                    unit: 'Shift Avg.',
                    icon: Icons.pie_chart,
                  ),
                  _TelemetryMetric(
                    label: 'Health',
                    value: '98.2%',
                    progress: 0.98,
                    unit: 'Optimal',
                    icon: Icons.monitor_heart,
                    color: AppTheme.sageGreen,
                  ),
                  _TelemetryMetric(
                    label: 'RUL (Cycles)',
                    value: '1,420 Left',
                    progress: 0.85,
                    unit: 'Est. 14 Days',
                    icon: Icons.hourglass_empty,
                  ),
                  _TelemetryMetric(
                    label: 'Failure Prob.',
                    value: '0.02%',
                    progress: 0.05,
                    unit: 'Very Low',
                    icon: Icons.shield,
                    color: Colors.blueAccent,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TelemetryMetric extends StatelessWidget {
  final String label;
  final String value;
  final double progress;
  final String unit;
  final IconData icon;
  final Color? color;

  const _TelemetryMetric({
    required this.label,
    required this.value,
    required this.progress,
    required this.unit,
    required this.icon,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final activeColor = color ?? AppTheme.sageGreen;

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceLayer.withOpacity(0.3),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Icon(icon, size: 16, color: activeColor),
              const SizedBox(width: 10),
              Text(
                label,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textMuted,
                    ),
              ),
              const Spacer(),
              Text(
                value,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textMain,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              backgroundColor: Colors.white,
              valueColor: AlwaysStoppedAnimation<Color>(activeColor.withOpacity(0.6)),
              minHeight: 6,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              Text(
                unit,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontSize: 10,
                      color: AppTheme.textMuted.withOpacity(0.6),
                      fontWeight: FontWeight.w500,
                    ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
