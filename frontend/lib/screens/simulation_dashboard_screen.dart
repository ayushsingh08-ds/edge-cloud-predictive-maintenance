import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../components/neumorphic_theme.dart';
import '../models/models.dart';
import '../providers/simulation_provider.dart';

class SimulationDashboardScreen extends StatelessWidget {
  const SimulationDashboardScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: NeumorphicColors.background,
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(80),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          decoration: NeumorphicTheme.decoration(borderRadius: BorderRadius.zero),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.arrow_back_ios, color: NeumorphicColors.accent),
                    onPressed: () => Navigator.pop(context),
                  ),
                  const Text(
                    'Simulation Dashboard',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: NeumorphicColors.accent),
                  ),
                ],
              ),
              Row(
                children: [
                   const Text('Live Connection Status: ', style: TextStyle(color: NeumorphicColors.text)),
                   const Icon(Icons.circle, color: Colors.green, size: 12),
                   const SizedBox(width: 4),
                   const Text('Connected', style: TextStyle(color: Colors.green, fontWeight: FontWeight.bold)),
                ],
              ),
            ],
          ),
        ),
      ),
      body: Consumer<SimulationProvider>(
        builder: (context, provider, child) {
          final metrics = provider.machineMetrics.values.toList();
          
          if (metrics.isEmpty) {
            return Center(
              child: NeumorphicButton(
                onPressed: () => provider.startSimulation(),
                child: const Text('Start Simulation Stream'),
              ),
            );
          }

          return GridView.builder(
            padding: const EdgeInsets.all(24),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3,
              crossAxisSpacing: 24,
              mainAxisSpacing: 24,
              childAspectRatio: 1.5,
            ),
            itemCount: metrics.length,
            itemBuilder: (context, index) {
              return MachineStatusCard(metrics: metrics[index]);
            },
          );
        },
      ),
    );
  }
}

class MachineStatusCard extends StatelessWidget {
  final MachineMetrics metrics;

  const MachineStatusCard({required this.metrics, Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return NeumorphicCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                metrics.machineId.toUpperCase(),
                style: const TextStyle(fontWeight: FontWeight.bold, color: NeumorphicColors.accent),
              ),
              _buildStatusIndicator(metrics.status),
            ],
          ),
          const Spacer(),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildMetric('Health', '${metrics.healthIndex.toStringAsFixed(1)}%', Icons.favorite),
              _buildMetric('RUL', '${metrics.remainingUsefulLife.toStringAsFixed(0)}h', Icons.timer),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildMetric('Queue', '${metrics.queueLength}', Icons.list),
              _buildMetric('Total', '${metrics.productionCount}', Icons.inventory),
            ],
          ),
          const SizedBox(height: 16),
          LinearProgressIndicator(
            value: metrics.healthIndex / 100,
            backgroundColor: NeumorphicColors.darkShadow.withOpacity(0.3),
            valueColor: AlwaysStoppedAnimation<Color>(_getHealthColor(metrics.healthIndex)),
            minHeight: 8,
            borderRadius: BorderRadius.circular(4),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusIndicator(MachineStatus status) {
    Color color;
    switch (status) {
      case MachineStatus.idle: color = NeumorphicColors.machineIdle; break;
      case MachineStatus.busy: color = NeumorphicColors.machineBusy; break;
      case MachineStatus.failed: color = NeumorphicColors.machineFailed; break;
      case MachineStatus.maintenance: color = NeumorphicColors.machineMaintenance; break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.2),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color),
      ),
      child: Text(
        status.label,
        style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.bold),
      ),
    );
  }

  Widget _buildMetric(String label, String value, IconData icon) {
    return Row(
      children: [
        Icon(icon, size: 16, color: NeumorphicColors.text.withOpacity(0.6)),
        const SizedBox(width: 8),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(fontSize: 10, color: NeumorphicColors.text)),
            Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: NeumorphicColors.text)),
          ],
        ),
      ],
    );
  }

  Color _getHealthColor(double value) {
    if (value > 80) return Colors.greenAccent;
    if (value > 50) return Colors.orangeAccent;
    return Colors.redAccent;
  }
}
