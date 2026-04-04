import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/simulation_provider.dart';
import 'neumorphic_theme.dart';

class BottomPanel extends StatelessWidget {
  const BottomPanel({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<SimulationProvider>(context);
    final metrics = provider.globalMetrics;

    return Container(
      height: 60,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: NeumorphicTheme.decoration(borderRadius: BorderRadius.zero),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              _buildMetricItem('Env Time', '${metrics?.environmentTime.toStringAsFixed(1) ?? '0.0'}s'),
              _buildDivider(),
              _buildMetricItem('OEE', '${((metrics?.oee ?? 0.0) * 100).toStringAsFixed(1)}%'),
              _buildDivider(),
              _buildMetricItem('Availability', '${((metrics?.availability ?? 0.0) * 100).toStringAsFixed(1)}%'),
              _buildDivider(),
              _buildMetricItem('Throughput', '${metrics?.completedJobs ?? 0} jobs'),
            ],
          ),
          Row(
            children: [
              const Icon(Icons.notifications_outlined, size: 18, color: NeumorphicColors.accent),
              const SizedBox(width: 8),
              const Text('System Status: ', style: TextStyle(fontSize: 12, color: NeumorphicColors.text)),
              Text(
                provider.isSimulating ? 'RUNNING' : 'PAUSED',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: provider.isSimulating ? Colors.green : Colors.orange,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetricItem(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16.0),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 10, color: NeumorphicColors.text, fontWeight: FontWeight.bold)),
          Text(value, style: const TextStyle(fontSize: 14, color: NeumorphicColors.accent, fontWeight: FontWeight.w900)),
        ],
      ),
    );
  }

  Widget _buildDivider() {
    return Container(width: 1, height: 24, color: NeumorphicColors.darkShadow.withOpacity(0.3));
  }
}
