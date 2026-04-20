import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/layout_provider.dart';
import '../providers/simulation_provider.dart';
import '../components/neumorphic_theme.dart';
import '../models/models.dart';

class SimulationDashboardScreen extends StatefulWidget {
  const SimulationDashboardScreen({Key? key}) : super(key: key);

  @override
  State<SimulationDashboardScreen> createState() => _SimulationDashboardScreenState();
}

class _SimulationDashboardScreenState extends State<SimulationDashboardScreen> {
  String _searchQuery = '';
  String _statusFilter = 'ALL';

  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    final simulation = Provider.of<SimulationProvider>(context);
    final isDark = layout.isDarkMode;

    final allMetrics = simulation.machineMetrics.values.toList()
      ..sort((a, b) => a.machineId.compareTo(b.machineId));

    final filteredMetrics = allMetrics.where((m) {
      final matchesSearch = m.machineId.toLowerCase().contains(_searchQuery.toLowerCase());
      final matchesFilter = _statusFilter == 'ALL' || m.status.label.toUpperCase() == _statusFilter;
      return matchesSearch && matchesFilter;
    }).toList();

    return Scaffold(
      backgroundColor: NeumorphicColors.background(isDark),
      body: Column(
        children: [
          _buildHeader(context, isDark),
          if (simulation.machineMetrics.isNotEmpty) _buildFilterBar(isDark),
          Expanded(
            child: simulation.machineMetrics.isEmpty
                ? _buildEmptyState(simulation, isDark)
                : CustomScrollView(
                    slivers: [
                      SliverPadding(
                        padding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
                        sliver: SliverToBoxAdapter(
                          child: _buildGlobalTrends(simulation, isDark),
                        ),
                      ),
                      SliverPadding(
                        padding: const EdgeInsets.all(24),
                        sliver: SliverGrid(
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 3,
                            crossAxisSpacing: 20,
                            mainAxisSpacing: 20,
                            childAspectRatio: 1.45,
                          ),
                          delegate: SliverChildBuilderDelegate(
                            (context, index) {
                              return MachineStatusCard(
                                key: ValueKey(filteredMetrics[index].machineId),
                                metrics: filteredMetrics[index],
                              );
                            },
                            childCount: filteredMetrics.length,
                          ),
                        ),
                      ),
                      if (filteredMetrics.isEmpty)
                        SliverFillRemaining(
                          hasScrollBody: false,
                          child: Center(
                            child: Text(
                              'NO MATCHES FOUND',
                              style: TextStyle(
                                fontWeight: FontWeight.w900,
                                color: NeumorphicColors.accent(isDark).withOpacity(0.3),
                                letterSpacing: 2.0,
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterBar(bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      child: Row(
        children: [
          Expanded(
            flex: 2,
            child: Container(
              height: 40,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              decoration: NeumorphicTheme.decoration(isDark: isDark, borderRadius: BorderRadius.circular(12)),
              child: Row(
                children: [
                  Icon(Icons.search, size: 16, color: NeumorphicColors.accent(isDark).withOpacity(0.5)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      onChanged: (val) => setState(() => _searchQuery = val),
                      style: TextStyle(fontSize: 12, color: NeumorphicColors.text(isDark)),
                      decoration: InputDecoration(
                        hintText: 'SEARCH NODE ID...',
                        hintStyle: TextStyle(fontSize: 10, color: NeumorphicColors.text(isDark).withOpacity(0.3), fontWeight: FontWeight.bold),
                        border: InputBorder.none,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 24),
          Row(
            children: ['ALL', 'IDLE', 'BUSY', 'FAILED', 'MAINTENANCE'].map((f) {
              final isSelected = _statusFilter == f;
              return Padding(
                padding: const EdgeInsets.only(left: 12),
                child: NeumorphicButton(
                  padding: 8.0,
                  borderRadius: 10,
                  onPressed: () => setState(() => _statusFilter = f),
                  child: Text(
                    f,
                    style: TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w900,
                      color: isSelected ? NeumorphicColors.accent(isDark) : NeumorphicColors.text(isDark).withOpacity(0.5),
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context, bool isDark) {
    return Container(
      padding: const EdgeInsets.fromLTRB(24, 48, 24, 16),
      decoration: NeumorphicTheme.decoration(isDark: isDark, borderRadius: BorderRadius.zero),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              IconButton(
                icon: Icon(Icons.arrow_back_ios, color: NeumorphicColors.accent(isDark), size: 20),
                onPressed: () => Navigator.pop(context),
              ),
              const SizedBox(width: 8),
              Text(
                'INDUSTRIAL CONTROL CENTER',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w900,
                  color: NeumorphicColors.accent(isDark),
                  letterSpacing: -0.5,
                ),
              ),
            ],
          ),
          _buildConnectionStatus(isDark),
        ],
      ),
    );
  }

  Widget _buildConnectionStatus(bool isDark) {
    return Consumer<SimulationProvider>(
      builder: (context, provider, child) {
        final isConnected = provider.backendConnected;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: NeumorphicTheme.decoration(isDark: isDark, borderRadius: BorderRadius.circular(20)),
          child: Row(
            children: [
              Icon(Icons.circle, color: isConnected ? Colors.greenAccent : Colors.redAccent, size: 10),
              const SizedBox(width: 8),
              Text(
                isConnected ? 'SYSTEM ONLINE' : 'NODE DOWN',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w900,
                  color: isConnected ? Colors.greenAccent : Colors.redAccent,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildGlobalTrends(SimulationProvider provider, bool isDark) {
    return Row(
      children: [
        Expanded(child: _buildTrendCard('THROUGHPUT', provider.throughputHistory, '${provider.globalMetrics?.throughput.toStringAsFixed(1) ?? "0.0"}/hr', isDark)),
        const SizedBox(width: 20),
        Expanded(child: _buildTrendCard('AVG CYCLE TIME', provider.cycleTimeHistory, '${(provider.globalMetrics?.avgCycleTime ?? 0).toStringAsFixed(1)}s', isDark)),
        const SizedBox(width: 20),
        Expanded(child: _buildTrendCard('WIP CONGESTION', provider.wipHistory.map((e) => e.toDouble()).toList(), '${provider.globalMetrics?.wip ?? 0}', isDark)),
      ],
    );
  }

  Widget _buildTrendCard(String title, List<double> values, String current, bool isDark) {
    return NeumorphicCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(title, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w900, color: NeumorphicColors.accent(isDark).withOpacity(0.6))),
              Text(current, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: NeumorphicColors.accent(isDark))),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 40,
            width: double.infinity,
            child: CustomPaint(
              painter: SparklinePainter(values: values, color: NeumorphicColors.accent(isDark)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(SimulationProvider provider, bool isDark) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.monitor_heart_outlined, size: 80, color: NeumorphicColors.accent(isDark).withOpacity(0.2)),
          const SizedBox(height: 24),
          const Text('TELEMETRY PIPELINE EMPTY', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.2)),
          const SizedBox(height: 32),
          NeumorphicButton(
            onPressed: () => provider.startSimulation(),
            child: const Text('ENGAGE SIMULATION RUN'),
          ),
        ],
      ),
    );
  }
}

class SparklinePainter extends CustomPainter {
  final List<double> values;
  final Color color;
  SparklinePainter({required this.values, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) return;
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final path = Path();
    final double maxVal = values.reduce(math.max);
    final double minVal = values.reduce(math.min);
    final double range = (maxVal - minVal).abs() < 0.001 ? 1.0 : maxVal - minVal;

    for (int i = 0; i < values.length; i++) {
      final double x = (size.width / (values.length - 1)) * i;
      final double y = size.height - ((values[i] - minVal) / range * size.height);
      if (i == 0) path.moveTo(x, y);
      else path.lineTo(x, y);
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}

class MachineStatusCard extends StatelessWidget {
  final MachineMetrics metrics;

  const MachineStatusCard({required this.metrics, Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final isDark = Provider.of<LayoutProvider>(context).isDarkMode;
    return NeumorphicCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                metrics.machineId.toUpperCase(),
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: NeumorphicColors.accent(isDark),
                ),
              ),
              _buildStatusIndicator(metrics.status, isDark),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildMetric(
                'Health',
                '${metrics.healthIndex.toStringAsFixed(1)}%',
                Icons.favorite,
                isDark,
              ),
              _buildMetric(
                'RUL',
                '${metrics.remainingUsefulLife.toStringAsFixed(0)}h',
                Icons.timer,
                isDark,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildMetric('Queue', '${metrics.queueLength}', Icons.list, isDark),
              if (metrics.scheduledMaintenance != null)
                _buildMetric(
                  'Maint In', 
                  '${(metrics.scheduledMaintenance! / 60).toStringAsFixed(0)}m', 
                  Icons.event_available,
                  isDark,
                  color: Colors.blueAccent
                )
              else
                _buildMetric(
                  'Risk',
                  '${(metrics.congestionRisk * 100).toStringAsFixed(0)}%',
                  Icons.warning_amber_rounded,
                  isDark,
                  color: metrics.congestionRisk > 0.7 ? Colors.redAccent : (metrics.congestionRisk > 0.4 ? Colors.orangeAccent : null),
                ),
            ],
          ),
          const SizedBox(height: 8),
          ExcludeSemantics(
            child: LinearProgressIndicator(
              value: metrics.healthIndex / 100,
              backgroundColor: NeumorphicColors.darkShadow(isDark).withOpacity(0.3),
              valueColor: AlwaysStoppedAnimation<Color>(
                _getHealthColor(metrics.healthIndex),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusIndicator(MachineStatus status, bool isDark) {
    Color color;
    switch (status) {
      case MachineStatus.idle:
        color = NeumorphicColors.machineIdle(isDark);
        break;
      case MachineStatus.busy:
        color = NeumorphicColors.machineBusy(isDark);
        break;
      case MachineStatus.failed:
        color = NeumorphicColors.machineFailed(isDark);
        break;
      case MachineStatus.maintenance:
        color = NeumorphicColors.machineMaintenance(isDark);
        break;
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
        style: TextStyle(
          fontSize: 10,
          color: color,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildMetric(String label, String value, IconData icon, bool isDark, {Color? color}) {
    return Row(
      children: [
        Icon(icon, size: 16, color: color ?? NeumorphicColors.text(isDark).withOpacity(0.6)),
        const SizedBox(width: 8),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                color: NeumorphicColors.text(isDark),
              ),
            ),
            Text(
              value,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: color ?? NeumorphicColors.text(isDark),
              ),
            ),
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
