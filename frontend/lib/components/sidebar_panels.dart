import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../providers/layout_provider.dart';
import '../providers/simulation_provider.dart';
import 'neumorphic_theme.dart';

class FactorySidebar extends StatelessWidget {
  const FactorySidebar({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    return Container(
      width: 110,
      decoration: BoxDecoration(
        color: NeumorphicColors.background(layout.isDarkMode),
        border: Border(
          right: BorderSide(
            color: layout.isDarkMode ? Colors.white10 : Colors.black12,
            width: 1,
          ),
        ),
      ),
      child: Column(
        children: [
          const SizedBox(height: 20),
          if (layout.activeMode == AppMode.showcase) ...[
            _buildSidebarLabel('SCENARIOS', layout.isDarkMode),
            const SizedBox(height: 12),
            Expanded(
              flex: 4,
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 10),
                children: [
                  _buildScenarioItem(
                    context,
                    'balanced_baseline',
                    'Balanced',
                    'Standard throughput flow.',
                    Icons.account_tree_outlined,
                  ),
                  _buildScenarioItem(
                    context,
                    'bottleneck_stress',
                    'Bottleneck',
                    'High-load stress test.',
                    Icons.speed_outlined,
                  ),
                  _buildScenarioItem(
                    context,
                    'failure_prone',
                    'Fragile',
                    'Downstream failure risks.',
                    Icons.warning_amber_outlined,
                  ),
                  _buildScenarioItem(
                    context,
                    'dynamic_routing',
                    'Dynamic',
                    'Fail-over & resilience.',
                    Icons.alt_route_rounded,
                  ),
                ],
              ),
            ),
          ],
          if (layout.activeMode == AppMode.engineering) ...[
            _buildSidebarLabel('PALETTE', layout.isDarkMode),
            const SizedBox(height: 12),
            Expanded(
              flex: 4,
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                children: LayoutNodeType.values
                    .where((t) => t != LayoutNodeType.conveyor)
                    .map((type) {
                      return DraggableComponent(type: type);
                    })
                    .toList(),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSidebarLabel(String text, bool isDark) {
    return Text(
      text,
      style: TextStyle(
        fontSize: 9,
        fontWeight: FontWeight.w900,
        color: NeumorphicColors.accent(isDark),
        letterSpacing: 1.5,
      ),
    );
  }

  Widget _buildScenarioItem(
    BuildContext context,
    String id,
    String label,
    String subtitle,
    IconData icon,
  ) {
    final simulation = Provider.of<SimulationProvider>(context);
    final layout = Provider.of<LayoutProvider>(context);
    final isDark = layout.isDarkMode;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12.0),
      child: NeumorphicButton(
        padding: 8,
        borderRadius: 12,
        onPressed: () => simulation.loadScenario(id),
        child: Column(
          children: [
            Icon(icon, size: 20, color: NeumorphicColors.accent(isDark)),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 8,
                fontWeight: FontWeight.bold,
                color: NeumorphicColors.text(isDark),
              ),
            ),
            const SizedBox(height: 2),
            Text(
              subtitle.toUpperCase(),
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 6,
                fontWeight: FontWeight.w900,
                color: NeumorphicColors.accent(isDark).withOpacity(0.6),
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class DraggableComponent extends StatelessWidget {
  final LayoutNodeType type;
  const DraggableComponent({required this.type, Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Draggable<LayoutNodeType>(
        data: type,
        feedback: Material(
          color: Colors.transparent,
          child: Container(
            width: 70,
            height: 70,
            decoration: NeumorphicTheme.decoration(
              isDark: layout.isDarkMode,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Icon(
              _getIconForType(type),
              color: NeumorphicColors.accent(layout.isDarkMode),
              size: 28,
            ),
          ),
        ),
        child: NeumorphicButton(
          padding: 12,
          borderRadius: 16,
          onPressed: () {
            final layout = Provider.of<LayoutProvider>(context, listen: false);
            layout.addNode(type, const Offset(4000, 4000));
          },
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                _getIconForType(type),
                color: NeumorphicColors.accent(layout.isDarkMode),
                size: 22,
              ),
              const SizedBox(height: 6),
              Text(
                type.value.toUpperCase(),
                style: TextStyle(
                  fontSize: 8,
                  fontWeight: FontWeight.w900,
                  color: NeumorphicColors.text(layout.isDarkMode),
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _getIconForType(LayoutNodeType type) {
    switch (type) {
      case LayoutNodeType.machine:
        return Icons.settings_suggest_outlined;
      case LayoutNodeType.buffer:
        return Icons.inventory_2_outlined;
      case LayoutNodeType.source:
        return Icons.login_outlined;
      case LayoutNodeType.sink:
        return Icons.logout_outlined;
      case LayoutNodeType.divider:
        return Icons.alt_route_outlined;
      case LayoutNodeType.conveyor:
        return Icons.sync_alt;
    }
  }
}

class PropertiesPanel extends StatelessWidget {
  const PropertiesPanel({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    final simulation = Provider.of<SimulationProvider>(context);
    final isDark = layout.isDarkMode;
    final selectedNodeId = layout.selectedNodeIds.isNotEmpty
        ? layout.selectedNodeIds.first
        : null;
    LayoutNode? node;
    if (selectedNodeId != null) {
      try {
        node = layout.nodes.firstWhere((n) => n.id == selectedNodeId);
      } catch (_) {
        node = null;
      }
    }
    final metrics = selectedNodeId != null
        ? (simulation.machineMetrics[selectedNodeId] ??
              simulation.machineMetrics[selectedNodeId.toLowerCase()])
        : null;

    return Container(
      width: 320,
      margin: const EdgeInsets.all(16),
      decoration: NeumorphicTheme.decoration(
        isDark: isDark,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildPanelHeader(
            'Real-Time Intelligence',
            Icons.psychology_outlined,
            isDark,
          ),
          Expanded(
            child: ExcludeSemantics(
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  if (node != null) ...[
                    _buildSectionTitle(
                      'SELECTED NODE: ${node.id.toUpperCase()}',
                      isDark,
                    ),
                    const SizedBox(height: 12),
                    _buildNodeHeadsup(
                      node,
                      metrics,
                      simulation,
                      simulation.healthHistory[node.id] ??
                          simulation.healthHistory[node.id.toLowerCase()] ??
                          [100.0],
                      isDark,
                    ),
                    const SizedBox(height: 24),
                    if (node.type == LayoutNodeType.machine) ...[
                      _buildSectionTitle('MACHINE HEALTH TREND', isDark),
                      const SizedBox(height: 12),
                      _buildRULChart(
                        metrics,
                        simulation.healthHistory[node.id] ??
                            simulation.healthHistory[node.id.toLowerCase()] ??
                            [],
                        isDark,
                      ),
                      const SizedBox(height: 24),
                    ],
                  ],
                  _buildSectionTitle('FACTORY METRICS', isDark),
                  const SizedBox(height: 12),
                  _buildMiniTrend(
                    'THROUGHPUT',
                    simulation.throughputSpots,
                    Colors.greenAccent,
                    isDark,
                  ),
                  _buildMiniTrend(
                    'CYCLE TIME',
                    simulation.cycleTimeSpots,
                    Colors.blueAccent,
                    isDark,
                  ),
                  _buildMiniTrend(
                    'WIP',
                    simulation.wipSpots,
                    Colors.orangeAccent,
                    isDark,
                  ),
                  const SizedBox(height: 24),
                  _buildSectionTitle('BOTTLENECKS', isDark),
                  const SizedBox(height: 12),
                  _buildBottleneckList(simulation, layout, isDark),
                ],
              ),
            ),
          ),
          _buildMiniMap(isDark),
        ],
      ),
    );
  }

  Widget _buildPanelHeader(String title, IconData icon, bool isDark) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Icon(icon, color: NeumorphicColors.accent(isDark), size: 20),
          const SizedBox(width: 12),
          Text(
            title,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              color: NeumorphicColors.accent(isDark),
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionTitle(String title, bool isDark) {
    return Text(
      title,
      style: TextStyle(
        fontSize: 10,
        fontWeight: FontWeight.w900,
        color: NeumorphicColors.text(isDark).withOpacity(0.5),
        letterSpacing: 1.0,
      ),
    );
  }

  Widget _buildNodeHeadsup(
    LayoutNode node,
    MachineMetrics? metrics,
    SimulationProvider simulation,
    List<double> healthHistory,
    bool isDark,
  ) {
    simulation.refreshNodeQueueSize(node.id);
    final capacityRaw = node.properties['capacity'];
    final capacity = capacityRaw is num ? capacityRaw.toInt() : 40;
    final liveQueue = simulation.queueSizeForNode(
      node.id,
      fallback: metrics?.queueLength ?? node.queueSize,
    );

    return NeumorphicCard(
      padding: const EdgeInsets.all(16),
      borderRadius: 16,
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'REUL / HEALTH',
                style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.bold,
                  color: NeumorphicColors.text(isDark).withOpacity(0.8),
                ),
              ),
              Text(
                '${(metrics?.healthIndex ?? 100).toStringAsFixed(0)}%',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: Colors.greenAccent,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          SizedBox(
            height: 12,
            width: double.infinity,
            child: CustomPaint(
              painter: SparklinePainter(
                data: healthHistory,
                color: Colors.greenAccent,
                strokeWidth: 1.2,
              ),
            ),
          ),
          const SizedBox(height: 12),
          _buildStat('Queue', '$liveQueue/$capacity', isDark),
          _buildStat(
            'Load',
            '${((metrics?.utilization ?? 0) * 100).toStringAsFixed(0)}%',
            isDark,
          ),
          const Divider(height: 24),
          Row(
            children: [
              Icon(Icons.bolt, color: Colors.yellowAccent, size: 14),
              const SizedBox(width: 8),
              Text(
                'Energy: ${metrics?.energyTotal.toStringAsFixed(1) ?? "0.0"} kWh',
                style: TextStyle(fontSize: 10, color: NeumorphicColors.text(isDark)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(Icons.co2, color: Colors.greenAccent, size: 18),
              const SizedBox(width: 4),
              Text(
                'Carbon: ${metrics?.carbonTotal.toStringAsFixed(2) ?? "0.0"} kg',
                style: TextStyle(fontSize: 10, color: NeumorphicColors.text(isDark)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStat(String label, String value, bool isDark) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: NeumorphicColors.text(isDark),
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: NeumorphicColors.text(isDark),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRULChart(
    MachineMetrics? metrics,
    List<double> healthHistory,
    bool isDark,
  ) {
    return Container(
      height: 60,
      width: double.infinity,
      padding: const EdgeInsets.all(8),
      decoration: NeumorphicTheme.decoration(
        isDark: isDark,
        borderRadius: BorderRadius.circular(12),
        isPressed: true,
      ),
      child: CustomPaint(
        painter: SparklinePainter(
          data: healthHistory,
          color: Colors.greenAccent,
        ),
      ),
    );
  }

  Widget _buildMiniTrend(
    String label,
    List<FlSpot> data,
    Color color,
    bool isDark,
  ) {
    final now = DateTime.now().millisecondsSinceEpoch / 1000.0;
    final minX = now - 60.0;
    final filtered = data.where((spot) => spot.x >= minX).toList();

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 9,
              fontWeight: FontWeight.bold,
              color: NeumorphicColors.text(isDark).withOpacity(0.7),
            ),
          ),
          const SizedBox(height: 4),
          SizedBox(
            height: 34,
            child: RepaintBoundary(
              child: LineChart(
                LineChartData(
                  minX: minX,
                  maxX: now,
                  gridData: const FlGridData(show: false),
                  borderData: FlBorderData(show: false),
                  titlesData: const FlTitlesData(show: false),
                  lineTouchData: const LineTouchData(enabled: false),
                  lineBarsData: [
                    LineChartBarData(
                      spots: filtered,
                      isCurved: true,
                      color: color,
                      barWidth: 2,
                      dotData: const FlDotData(show: false),
                      belowBarData: BarAreaData(show: false),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBottleneckList(
    SimulationProvider simulation,
    LayoutProvider layout,
    bool isDark,
  ) {
    if (simulation.bottlenecks.isEmpty) {
      return Row(
        children: [
          const Icon(
            Icons.check_circle_outline,
            color: Colors.greenAccent,
            size: 16,
          ),
          const SizedBox(width: 8),
          Text(
            'No congestion detected.',
            style: TextStyle(
              fontSize: 10,
              color: NeumorphicColors.text(isDark).withOpacity(0.6),
            ),
          ),
        ],
      );
    }
    return Column(
      children: simulation.bottlenecks
          .map(
            (b) => _buildBottleneckItem(
              b,
              isDark,
              onTap: () => layout.focusOnNode(b),
            ),
          )
          .toList(),
    );
  }

  Widget _buildBottleneckItem(
    String machineId,
    bool isDark, {
    required VoidCallback onTap,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: GestureDetector(
        onTap: onTap,
        child: Row(
          children: [
            const Icon(
              Icons.warning_amber_rounded,
              color: Colors.orangeAccent,
              size: 14,
            ),
            const SizedBox(width: 8),
            Text(
              machineId,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: NeumorphicColors.text(isDark),
              ),
            ),
            const Spacer(),
            const Text(
              'FOCUS',
              style: TextStyle(
                fontSize: 8,
                color: Colors.cyanAccent,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMiniMap(bool isDark) {
    return Container(
      height: 120,
      margin: const EdgeInsets.all(20),
      decoration: NeumorphicTheme.decoration(
        isDark: isDark,
        borderRadius: BorderRadius.circular(16),
        isPressed: true,
      ),
      child: Center(
        child: Icon(
          Icons.map_outlined,
          color: NeumorphicColors.accent(isDark).withOpacity(0.1),
          size: 40,
        ),
      ),
    );
  }
}

class SparklinePainter extends CustomPainter {
  final List<double> data;
  final Color color;
  final double strokeWidth;

  SparklinePainter({
    required this.data,
    required this.color,
    this.strokeWidth = 2.0,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (data.length < 2) return;
    final paint = Paint()
      ..color = color
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final path = Path();
    final xStep = size.width / (data.length - 1);

    // Normalize logic
    double minVal = data.isEmpty ? 0 : data.reduce((a, b) => a < b ? a : b);
    double maxVal = data.isEmpty ? 100 : data.reduce((a, b) => a > b ? a : b);
    if (maxVal == minVal) maxVal += 1.0;

    final range = maxVal - minVal;

    for (int i = 0; i < data.length; i++) {
      final x = i * xStep;
      final y = size.height - ((data[i] - minVal) / range * size.height);
      if (i == 0)
        path.moveTo(x, y);
      else
        path.lineTo(x, y);
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant SparklinePainter oldDelegate) => true;
}
