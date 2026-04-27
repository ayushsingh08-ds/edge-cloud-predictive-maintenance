import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:vector_math/vector_math_64.dart' as v64;
import '../models/models.dart';
import '../providers/simulation_provider.dart';
import '../providers/layout_provider.dart';
import 'package:fl_chart/fl_chart.dart';
class Dashboard3DScreen extends StatefulWidget {
  const Dashboard3DScreen({super.key});

  @override
  State<Dashboard3DScreen> createState() => _Dashboard3DScreenState();
}

class _Dashboard3DScreenState extends State<Dashboard3DScreen> with TickerProviderStateMixin {
  final ValueNotifier<double> _rotationX = ValueNotifier(-0.6);
  final ValueNotifier<double> _rotationZ = ValueNotifier(0.5);
  final ValueNotifier<double> _zoom = ValueNotifier(0.8);
  String? _selectedMachineId;
  String _activeBottomTab = "Alerts";
  
  late AnimationController _pulseController;
  late AnimationController _cameraController;

  void _animateCameraTo(double targetX, double targetZ, double targetZoom) {
    final startX = _rotationX.value;
    final startZ = _rotationZ.value;
    final startZoom = _zoom.value;

    _cameraController.stop();
    _cameraController.reset();

    final animation = CurvedAnimation(parent: _cameraController, curve: Curves.easeInOutCubic);
    
    _cameraController.addListener(() {
      _rotationX.value = ui.lerpDouble(startX, targetX, animation.value)!;
      _rotationZ.value = ui.lerpDouble(startZ, targetZ, animation.value)!;
      _zoom.value = ui.lerpDouble(startZoom, targetZoom, animation.value)!;
    });

    _cameraController.forward();
  }

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);

    _cameraController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );

    WidgetsBinding.instance.addPostFrameCallback((_) {
      final layout = Provider.of<LayoutProvider>(context, listen: false);
      final sim = Provider.of<SimulationProvider>(context, listen: false);
      
      layout.initializeCatalog();
      sim.initialize();
      sim.onLayoutChanged = () => layout.refreshLayout(force: true);

      // Auto-load default scenario if nothing is loaded
      if (sim.currentScenarioId == null) {
        sim.loadScenario('balanced_baseline');
      } else {
        layout.refreshLayout(force: true);
      }
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _cameraController.dispose();
    _rotationX.dispose();
    _rotationZ.dispose();
    _zoom.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0C10),
      body: Stack(
        children: [
          // 1. The 3D Viewport & Nodes
          Positioned.fill(
            child: AnimatedBuilder(
              animation: Listenable.merge([_rotationX, _rotationZ, _zoom, _pulseController]),
              builder: (context, _) {
                return Stack(
                  children: [
                    Positioned.fill(child: _build3DViewport()),
                    Positioned.fill(child: IgnorePointer(child: _buildProjectedConnections())),
                    Positioned.fill(child: _buildProjectedNodes()),
                  ],
                );
              },
            ),
          ),

          // 2. Top Navigation & Global Stats (Glassmorphism)
          _buildTopBar(),

          // 3. Left Sidebar (Scenarios)
          _buildLeftSidebar(),

          // 4. Right Sidebar (Reasoning Panel & Intelligence)
          _buildRightSidebar(),

          // 5. Bottom HUD (Logs & Performance)
          _buildBottomHUD(),

          // 6. Viewport Controls (2D/3D toggle, Level Selector)
          _buildViewportControls(),
        ],
      ),
    );
  }

  Widget _buildViewportControls() {
    final layout = context.watch<LayoutProvider>();
    return Positioned(
      top: 100, left: 120,
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(color: Colors.black45, borderRadius: BorderRadius.circular(8), border: Border.all(color: Colors.white10)),
            child: Row(
              children: [
                _buildToggleBtn("2D", !layout.show3D, () => layout.toggle3D()),
                _buildToggleBtn("3D", layout.show3D, () => layout.toggle3D()),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(color: Colors.black45, borderRadius: BorderRadius.circular(8), border: Border.all(color: Colors.white10)),
            child: Row(
              children: [
                Text("Levels", style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 11, fontWeight: FontWeight.bold)),
                const SizedBox(width: 8),
                const Text("All Levels", style: TextStyle(color: Colors.white, fontSize: 12)),
                const Icon(Icons.arrow_drop_down, color: Colors.white, size: 16),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToggleBtn(String label, bool active, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        decoration: BoxDecoration(color: active ? Colors.white.withOpacity(0.1) : Colors.transparent, borderRadius: BorderRadius.circular(4)),
        child: Text(label, style: TextStyle(color: active ? Colors.white : Colors.white30, fontSize: 11, fontWeight: FontWeight.bold)),
      ),
    );
  }

  Widget _build3DViewport() {
    return GestureDetector(
      onPanUpdate: (details) {
        _rotationZ.value += details.delta.dx * 0.005;
        _rotationX.value = (_rotationX.value - details.delta.dy * 0.005).clamp(-math.pi / 2, 0.0);
      },
      child: Container(
        color: Colors.transparent,
        child: LayoutBuilder(
          builder: (context, constraints) {
            return Transform(
              alignment: Alignment.center,
              transform: Matrix4.identity()
                ..setEntry(3, 2, 0.001) // Perspective
                ..scale(_zoom.value)
                ..rotateX(_rotationX.value)
                ..rotateZ(_rotationZ.value),
              child: Stack(
                children: [
                  // Rendering 3 Levels
                  _buildLevel(1, "LEVEL 1: RAW & PREP", const Color(0xFF1A212B)),
                  _buildLevel(2, "LEVEL 2: PROCESSING", const Color(0xFF1E2733)),
                  _buildLevel(3, "LEVEL 3: ASSEMBLY", const Color(0xFF252D3D)),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildProjectedConnections() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final layout = context.watch<LayoutProvider>();
        final sim = context.watch<SimulationProvider>();
        final matrix = Matrix4.identity()
          ..setEntry(3, 2, 0.001) // Perspective
          ..scale(_zoom.value)
          ..rotateX(_rotationX.value)
          ..rotateZ(_rotationZ.value);

        return CustomPaint(
          size: Size(constraints.maxWidth, constraints.maxHeight),
          painter: _ProjectedConnectionPainter(
            edges: layout.edges,
            nodes: layout.nodes,
            cameraMatrix: matrix,
            activeParticles: sim.activeParticles,
            globalThroughput: sim.globalMetrics?.throughput ?? 0.0,
            pulse: _pulseController.value,
          ),
        );
      },
    );
  }

  Widget _buildLevel(int level, String label, Color color) {
    double zOffset = (level - 1) * -180.0;
    return Transform(
      transform: Matrix4.translationValues(0, 0, zOffset),
      child: Center(
        child: Container(
          width: 800,
          height: 600,
          decoration: BoxDecoration(
            color: color.withOpacity(0.08),
            border: Border.all(color: color.withOpacity(0.2), width: 1.5),
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(color: color.withOpacity(0.05), blurRadius: 40, spreadRadius: -10),
            ],
          ),
          child: Stack(
            children: [
              // Grid Background
              Positioned.fill(
                child: CustomPaint(painter: _GridPainter(color: color.withOpacity(0.1))),
              ),
              Positioned(
                left: 20,
                bottom: 20,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      "LEVEL $level",
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.2),
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.5,
                      ),
                    ),
                    Text(
                      label.split(':').last.trim(),
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.4),
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildProjectedNodes() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final layout = context.watch<LayoutProvider>();
        final sim = context.watch<SimulationProvider>();
        final matrix = Matrix4.identity()
          ..setEntry(3, 2, 0.001) // Perspective
          ..scale(_zoom.value)
          ..rotateX(_rotationX.value)
          ..rotateZ(_rotationZ.value);

        final centerX = constraints.maxWidth / 2;
        final centerY = constraints.maxHeight / 2;

        return Stack(
          clipBehavior: Clip.none,
          children: layout.nodes.map((node) {
            final level = node.level;
            final zOffset = (level - 1) * -180.0;
            
            final vec = v64.Vector4(
              node.position.x - 400,
              node.position.y - 300,
              zOffset - 20,
              1.0,
            );
            final transformed = matrix.transform(vec);
            final w = transformed.w == 0 ? 1.0 : transformed.w;
            
            final projectedX = centerX + transformed.x / w;
            final projectedY = centerY + transformed.y / w;

            final metrics = sim.machineMetrics[node.id.toLowerCase()];
            final isSelected = _selectedMachineId == node.id;
            final isBottleneck = sim.bottlenecks.contains(node.id);

            return AnimatedPositioned(
              duration: const Duration(milliseconds: 600),
              curve: Curves.easeInOutCubic,
              left: projectedX - 30, // Assuming _Machine3DComponent is 60 wide
              top: projectedY - 20,  // Assuming _Machine3DComponent is 40 tall
              child: GestureDetector(
                onTap: () {
                  setState(() => _selectedMachineId = node.id);
                  _animateCameraTo(-0.7, 0.4, 1.0); // Focus glide
                },
                behavior: HitTestBehavior.opaque,
                child: _Machine3DComponent(
                  node: node,
                  metrics: metrics,
                  isSelected: isSelected,
                  isBottleneck: isBottleneck,
                  pulse: _pulseController.value,
                  queueSize: sim.jobsAtNode(node.id).length,
                ),
              ),
            );
          }).toList(),
        );
      },
    );
  }

  // --- UI Overlays ---

  Widget _buildPillButton(String label, IconData icon, bool active) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: active ? Colors.white.withOpacity(0.1) : Colors.transparent,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        children: [
          Icon(icon, color: active ? Colors.white : Colors.white54, size: 14),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(color: active ? Colors.white : Colors.white54, fontSize: 11, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _buildTopBar() {
    final sim = context.watch<SimulationProvider>();
    final metrics = sim.globalMetrics;
    return Positioned(
      top: 0, left: 0, right: 0,
      child: Container(
        height: 80,
        padding: const EdgeInsets.symmetric(horizontal: 24),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Colors.black.withOpacity(0.8), Colors.transparent],
          ),
        ),
        child: Row(
          children: [
            Image.asset('assets/logo.png', height: 32, errorBuilder: (c, e, s) => const Icon(Icons.blur_on, color: Color(0xFF00E5FF), size: 32)),
            const SizedBox(width: 12),
            Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text("Digital Twin Showcase", style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                Text("Smart Factory", style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12)),
              ],
            ),
            const SizedBox(width: 32),
            
            // SHOWCASE / ENGINEERING Toggle Pill
            Container(
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.05),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: Colors.white10),
              ),
              child: Row(
                children: [
                  _buildPillButton("SHOWCASE", Icons.auto_awesome, true),
                  _buildPillButton("ENGINEERING", Icons.build, false),
                ],
              ),
            ),
            
            const Spacer(),
            
            _buildStatItem("THROUGHPUT", metrics?.throughput ?? 0.0, decimals: 1, suffix: " /hr"),
            _buildStatItem("UTILIZATION", (metrics?.avgUtilization ?? 0) * 100, suffix: "%"),
            _buildStatItem("OEE", (metrics?.oee ?? 0) * 100, suffix: "%"),
            _buildStatItem("CARBON", metrics?.totalCarbon ?? 0.0, decimals: 1, suffix: " kg", color: Colors.greenAccent),
            _buildStatItem("EFFICIENCY", metrics?.energyEfficiencyPct ?? 0.0, decimals: 1, suffix: "%", color: Colors.cyanAccent),
            _buildStatTextItem("QUBO SOLVER", metrics?.quboSolverState ?? "Heuristic", color: const Color(0xFF00E5FF)),
            
            const Spacer(),
            
            const Text("1x", style: TextStyle(color: Colors.white54, fontSize: 12)),
            SizedBox(
              width: 100,
              child: Slider(
                value: 1.0, // Will map to sim.speedMultiplier
                min: 1.0,
                max: 5.0,
                activeColor: const Color(0xFF00E5FF),
                inactiveColor: Colors.white24,
                onChanged: (v) {}, // sim.setSpeedMultiplier(v)
              ),
            ),
            const Text("5.0x", style: TextStyle(color: Colors.white54, fontSize: 12)),
            const SizedBox(width: 16),
            
            Container(
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.05),
                borderRadius: BorderRadius.circular(8),
              ),
              child: IconButton(
                icon: Icon(sim.isSimulating ? Icons.pause : Icons.play_arrow),
                color: const Color(0xFF00E5FF),
                onPressed: () => sim.toggleSimulation(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatTextItem(String label, String value, {Color? color}) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(label, style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 10, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(
            value.toUpperCase(),
            style: TextStyle(color: color ?? Colors.white, fontSize: 13, fontWeight: FontWeight.bold, letterSpacing: 1.0),
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(String label, double value, {int decimals = 0, String suffix = "", Color? color}) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(label, style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 10, fontWeight: FontWeight.bold)),
          CountUpText(
            value: value,
            decimals: decimals,
            suffix: suffix,
            style: TextStyle(color: color ?? Colors.white, fontSize: 16, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }

  String _generateSmartReasoning(MachineMetrics metrics) {
    if (metrics.isBuffer) {
      if (metrics.congestionRisk > 0.8) {
        return "Critical congestion detected. Buffer is near capacity (${(metrics.congestionRisk * 100).toInt()}%). Upstream throughput is exceeding downstream processing rate.";
      } else if (metrics.congestionRisk > 0.5) {
        return "Moderate load detected. Optimal flow maintained. No immediate action required.";
      } else {
        return "Buffer flow is stable. System throughput is balanced across this node.";
      }
    } else {
      if (metrics.healthIndex < 0.6) {
        return "Critical Alert! High wear detected on mechanical components. Predicted RUL is ${metrics.remainingUsefulLife.toInt()} hours. Recommend immediate inspection.";
      } else if (metrics.remainingUsefulLife < 300) {
        return "Degradation detected. Asset is entering aging phase. RUL is below nominal threshold.";
      } else {
        return "Machine is operating at peak efficiency. Internal sensor telemetry indicates nominal health status.";
      }
    }
  }

  Widget _buildRightSidebar() {
    final sim = context.watch<SimulationProvider>();
    final selectedMetrics = _selectedMachineId != null ? sim.machineMetrics[_selectedMachineId!.toLowerCase()] : null;

    return Positioned(
      top: 100, right: 24, bottom: 120,
      child: Container(
        width: 320,
        decoration: BoxDecoration(
          color: const Color(0xFF12161D).withOpacity(0.85),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white.withOpacity(0.1)),
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.5), blurRadius: 20)],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: BackdropFilter(
            filter: ColorFilter.mode(Colors.black.withOpacity(0.2), BlendMode.darken),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildSidebarHeader("Real-Time Intelligence"),
                    const SizedBox(height: 20),
                    _buildSidebarMetricRow("THROUGHPUT", sim.globalMetrics?.throughput ?? 0.0, " /hr", Colors.greenAccent, decimals: 1, hasChart: true, spots: sim.throughputSpots),
                    _buildSidebarMetricRow("CYCLE TIME", sim.globalMetrics?.avgCycleTime ?? 0.0, " s", Colors.blueAccent, decimals: 1, hasChart: true, spots: sim.cycleTimeSpots),
                    _buildSidebarMetricRow("WIP", (sim.globalMetrics?.wip ?? 0).toDouble(), "", Colors.orangeAccent, hasChart: true, spots: sim.wipSpots),
                    const Divider(height: 40, color: Colors.white10),
                    
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 400),
                      transitionBuilder: (child, animation) {
                        return FadeTransition(
                          opacity: animation,
                          child: SlideTransition(
                            position: Tween<Offset>(begin: const Offset(0.1, 0), end: Offset.zero).animate(CurvedAnimation(parent: animation, curve: Curves.easeOut)),
                            child: child,
                          ),
                        );
                      },
                      child: KeyedSubtree(
                        key: ValueKey(_selectedMachineId ?? "none"),
                        child: _buildIntelligenceContent(sim, selectedMetrics),
                      ),
                    ),

                    _buildSidebarHeader("BOTTLENECKS"),
                    const SizedBox(height: 12),
                    ..._buildBottleneckList(sim),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildIntelligenceContent(SimulationProvider sim, MachineMetrics? selectedMetrics) {
    if (_selectedMachineId != null) {
      if (selectedMetrics != null) {
        return Column(
          key: ValueKey(_selectedMachineId),
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSidebarHeader("Reasoning Panel", subtitle: selectedMetrics.isBuffer ? "LOGISTICS FLOW" : "SHAP EXPLAINER"),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.05),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.white.withOpacity(0.1)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.auto_awesome, color: Colors.cyanAccent, size: 14),
                      const SizedBox(width: 8),
                      Text("SMART REASONING", style: TextStyle(color: Colors.cyanAccent, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 1.2)),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _generateSmartReasoning(selectedMetrics),
                    style: TextStyle(color: Colors.white.withOpacity(0.85), fontSize: 11, height: 1.4),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            if (!selectedMetrics.isBuffer) ...[
              Text(
                "RUL is influenced by the following top contributors:",
                style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 11),
              ),
              const SizedBox(height: 16),
              ..._buildShapList(selectedMetrics.shapImportance),
              const SizedBox(height: 12),
              _buildConfidenceScore(selectedMetrics.confidenceScore),
            ] else ...[
              _buildSidebarMetricRow("CONGESTION", (selectedMetrics.congestionRisk * 100), "%", Colors.orangeAccent),
              _buildSidebarMetricRow("QUEUE SIZE", selectedMetrics.queueLength.toDouble(), "", Colors.blueAccent),
            ],
            const SizedBox(height: 40),
          ],
        );
      } else {
        return Column(
          children: const [
            SizedBox(height: 40),
            Center(child: CircularProgressIndicator(strokeWidth: 2, color: Colors.cyanAccent)),
            SizedBox(height: 20),
            Center(child: Text("Syncing Intelligence...", style: TextStyle(color: Colors.white30, fontSize: 10))),
            SizedBox(height: 40),
          ],
        );
      }
    } else {
      return Column(
        children: const [
          Center(child: Text("Select a machine to view XAI analytics", style: TextStyle(color: Colors.white30, fontSize: 12))),
          SizedBox(height: 40),
        ],
      );
    }
  }

  List<Widget> _buildBottleneckList(SimulationProvider sim) {
    final bottlenecks = sim.globalMetrics?.bottleneckNodes ?? [];
    if (bottlenecks.isEmpty) {
      return [const Center(child: Text("No critical bottlenecks detected.", style: TextStyle(color: Colors.white30, fontSize: 12)))];
    }
    
    return bottlenecks.map((nodeId) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          children: [
            const Icon(Icons.warning_amber, color: Colors.orangeAccent, size: 16),
            const SizedBox(width: 12),
            Expanded(child: Text(nodeId, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold))),
            TextButton(
              onPressed: () {
                setState(() => _selectedMachineId = nodeId);
                _animateCameraTo(-0.8, 0.2, 1.3); // Deep focus glide
              },
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                minimumSize: Size.zero,
                backgroundColor: Colors.white.withOpacity(0.05),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
              ),
              child: const Text("FOCUS", style: TextStyle(color: Colors.lightBlueAccent, fontSize: 10, fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      );
    }).toList();
  }

  List<Widget> _buildShapList(Map<String, double> shap) {
    final sorted = shap.entries.toList()..sort((a, b) => b.value.abs().compareTo(a.value.abs()));
    return sorted.take(3).map((e) {
      final isDamaging = e.value > 0;
      final color = isDamaging ? Colors.redAccent : Colors.greenAccent;
      final sign = isDamaging ? "+" : "";
      final index = sorted.indexOf(e);
      
      return AnimatedOpacity(
        duration: Duration(milliseconds: 300 + (index * 100)),
        opacity: 1.0,
        child: Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: Row(
            children: [
              Container(
                width: 32, height: 32,
                decoration: BoxDecoration(color: Colors.white.withOpacity(0.05), borderRadius: BorderRadius.circular(4)),
                child: Center(child: Text("${index + 1}", style: const TextStyle(color: Colors.white))),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(e.key.replaceAll('_', ' ').toUpperCase(), style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 6),
                    Container(
                      width: double.infinity,
                      height: 4,
                      decoration: BoxDecoration(color: Colors.white10, borderRadius: BorderRadius.circular(2)),
                      child: FractionallySizedBox(
                        alignment: Alignment.centerLeft,
                        widthFactor: (e.value.abs() / 100).clamp(0.0, 1.0),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 500),
                          decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2)),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              CountUpText(
                value: e.value,
                decimals: 1,
                suffix: "%",
                style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.bold),
              ),
            ],
          ),
        ),
      );
    }).toList();
  }

  Widget _buildSidebarHeader(String title, {String? subtitle}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            const Icon(Icons.psychology, color: Color(0xFF00E5FF), size: 18),
            const SizedBox(width: 8),
            Text(title, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold)),
          ],
        ),
        if (subtitle != null) Text(subtitle, style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 9, fontWeight: FontWeight.bold)),
      ],
    );
  }

  Widget _buildSidebarMetricRow(String label, double value, String suffix, Color color, {int decimals = 0, bool hasChart = false, List<FlSpot>? spots}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 10, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                CountUpText(
                  value: value,
                  decimals: decimals,
                  suffix: suffix,
                  style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ],
            ),
          ),
          if (hasChart && spots != null)
            SizedBox(
              width: 100,
              height: 40,
              child: CustomPaint(
                painter: _MiniChartPainter(color: color, spots: spots),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildConfidenceScore(double score) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: Colors.black26, borderRadius: BorderRadius.circular(8)),
      child: Row(
        children: [
          const Text("Model Confidence", style: TextStyle(color: Colors.white60, fontSize: 11)),
          const Spacer(),
          Text("${(score * 100).toInt()}%", style: const TextStyle(color: Color(0xFF00E5FF), fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _buildLeftSidebar() {
    final sim = context.watch<SimulationProvider>();
    return Positioned(
      top: 100,
      left: 24,
      bottom: 120,
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("SCENARIOS", style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 1.2)),
            const SizedBox(height: 16),
            _buildScenarioButton(
              "Balanced",
              "STANDARD\nTHROUGHPUT\nFLOW.",
              Icons.account_tree,
              sim.currentScenarioId == 'balanced_baseline',
              () => sim.loadScenario('balanced_baseline'),
              const Color(0xFFFFB74D), // Golden color for Balanced
            ),
            _buildScenarioButton(
              "Bottleneck",
              "HIGH-LOAD\nSTRESS TEST.",
              Icons.hourglass_bottom,
              sim.currentScenarioId == 'bottleneck_stress',
              () => sim.loadScenario('bottleneck_stress'),
              const Color(0xFFFFB74D),
            ),
            _buildScenarioButton(
              "Fragile",
              "DOWNSTREAM\nFAILURE RISKS.",
              Icons.warning_amber,
              sim.currentScenarioId == 'failure_prone',
              () => sim.loadScenario('failure_prone'),
              const Color(0xFFFFB74D),
            ),
            _buildScenarioButton(
              "Dynamic",
              "FAIL-OVER &\nRESILIENCE.",
              Icons.merge_type,
              sim.currentScenarioId == 'dynamic_routing',
              () => sim.loadScenario('dynamic_routing'),
              const Color(0xFF00E5FF),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildScenarioButton(
    String title,
    String sub,
    IconData icon,
    bool active,
    VoidCallback onTap,
    Color themeColor,
  ) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 120,
        height: 160,
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: active ? themeColor.withOpacity(0.1) : Colors.white.withOpacity(0.02),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: active ? themeColor : Colors.white10,
            width: active ? 1.5 : 1.0,
          ),
          boxShadow: active
              ? [BoxShadow(color: themeColor.withOpacity(0.2), blurRadius: 20, spreadRadius: -5)]
              : [],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: active ? themeColor : Colors.white30, size: 24),
            const SizedBox(height: 12),
            Text(
              title,
              style: TextStyle(
                color: active ? Colors.white : Colors.white70,
                fontSize: 12,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              sub,
              style: TextStyle(
                color: Colors.white.withOpacity(0.4),
                fontSize: 8,
                height: 1.4,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBottomHUD() {
    final sim = context.watch<SimulationProvider>();
    final metrics = sim.globalMetrics;
    return Positioned(
      bottom: 24,
      left: 24,
      right: 24,
      child: Container(
        height: 180,
        decoration: BoxDecoration(
          color: const Color(0xFF12161D).withOpacity(0.9),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white10),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.5),
              blurRadius: 20,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: Column(
          children: [
            // Tab Header
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: Colors.white10)),
              ),
              child: Row(
                children: [
                  _buildHUDTab("Alerts", sim.alertsFeed.length),
                  _buildHUDTab("Logs", null),
                  _buildHUDTab("Events", null),
                  _buildHUDTab("Scenarios", null),
                  const Spacer(),
                  _buildHUDStat(
                    "Throughput",
                    "${metrics?.throughput.toStringAsFixed(1) ?? '0.0'} /hr",
                  ),
                  _buildHUDStat(
                    "OEE",
                    "${((metrics?.oee ?? 0) * 100).toInt()}%",
                  ),
                  _buildHUDStat("Energy", "333 kWh", color: Colors.yellowAccent, icon: Icons.bolt),
                  _buildHUDStat("CO2", "149.9 kg", color: Colors.cyanAccent, icon: Icons.cloud),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.orangeAccent.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: Colors.orangeAccent),
                    ),
                    child: Text(
                      sim.isSimulating ? "RUNNING" : "PAUSED",
                      style: const TextStyle(
                        color: Colors.orangeAccent,
                        fontWeight: FontWeight.bold,
                        fontSize: 10,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            // Feed Content
            Expanded(
              child:
                  _activeBottomTab == "Scenarios"
                      ? _buildScenarioList(sim)
                      : _buildFeedList(sim),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHUDTab(String label, int? badge) {
    final active = _activeBottomTab == label;
    return GestureDetector(
      onTap: () => setState(() => _activeBottomTab = label),
      child: Container(
        margin: const EdgeInsets.only(right: 24),
        child: Row(
          children: [
            Text(
              label,
              style: TextStyle(
                color: active ? Colors.white : Colors.white38,
                fontSize: 12,
                fontWeight: active ? FontWeight.bold : FontWeight.normal,
              ),
            ),
            if (badge != null && badge > 0) ...[
              const SizedBox(width: 6),
              AnimatedScale(
                scale: 1.0,
                duration: const Duration(milliseconds: 200),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.redAccent,
                    borderRadius: BorderRadius.circular(10),
                    boxShadow: const [BoxShadow(color: Colors.redAccent, blurRadius: 4)],
                  ),
                  child: Text(
                    "$badge",
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 9,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildHUDStat(String label, String value, {Color? color, IconData? icon}) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          if (icon != null) ...[
            Icon(icon, color: color ?? Colors.white, size: 16),
            const SizedBox(width: 8),
          ],
          Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 9),
              ),
              Text(
                value,
                style: TextStyle(
                  color: color ?? Colors.white,
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildFeedList(SimulationProvider sim) {
    List<dynamic> feed = [];
    if (_activeBottomTab == "Alerts") feed = sim.alertsFeed;
    if (_activeBottomTab == "Logs") feed = sim.logsFeed;
    if (_activeBottomTab == "Events") feed = sim.eventsFeed;

    if (feed.isEmpty) {
      return Center(
        child: Text(
          "No $_activeBottomTab entries available.",
          style: const TextStyle(color: Colors.white24, fontSize: 12),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: feed.length,
      itemBuilder: (context, index) {
        final item = feed[feed.length - 1 - index];
        final type = item['event_type'] ?? 'INFO';
        final msg = item['message'] ?? '';
        final ts = item['timestamp']?.toString().split('T').last.split('.').first ?? '';

        return TweenAnimationBuilder<double>(
          key: ValueKey(item['id'] ?? index),
          tween: Tween(begin: 0.0, end: 1.0),
          duration: const Duration(milliseconds: 300),
          builder: (context, value, child) {
            return Opacity(
              opacity: value,
              child: Transform.translate(
                offset: Offset(0, 10 * (1 - value)),
                child: child,
              ),
            );
          },
          child: Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    color: type == "ALERT" ? Colors.redAccent : (type == "WARNING" ? Colors.orangeAccent : Colors.cyanAccent),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(color: (type == "ALERT" ? Colors.redAccent : Colors.orangeAccent).withOpacity(0.4), blurRadius: 4),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        type,
                        style: TextStyle(
                          color: type == "ALERT" ? Colors.redAccent : Colors.white70,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        msg,
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.6),
                          fontSize: 10,
                        ),
                      ),
                    ],
                  ),
                ),
                Text(
                  ts,
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.2),
                    fontSize: 10,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildScenarioList(SimulationProvider sim) {
    final scenarios = [
      {'id': 'balanced_baseline', 'name': 'Balanced Baseline'},
      {'id': 'bottleneck_stress', 'name': 'Bottleneck Stress'},
      {'id': 'failure_prone', 'name': 'Fragile Paths'},
      {'id': 'dynamic_routing', 'name': 'Dynamic Fail-over'},
    ];

    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: scenarios.length,
      itemBuilder: (context, index) {
        final s = scenarios[index];
        final active = sim.currentScenarioId == s['id'];
        return ListTile(
          dense: true,
          title: Text(
            s['name']!,
            style: TextStyle(
              color: active ? const Color(0xFF00E5FF) : Colors.white70,
              fontSize: 12,
            ),
          ),
          trailing:
              active
                  ? const Icon(
                    Icons.check_circle,
                    color: Color(0xFF00E5FF),
                    size: 16,
                  )
                  : null,
          onTap: () => sim.loadScenario(s['id']!),
        );
      },
    );
  }
}

class _Machine3DComponent extends StatelessWidget {
  final LayoutNode node;
  final MachineMetrics? metrics;
  final bool isSelected;
  final bool isBottleneck;
  final double pulse;
  final int queueSize;

  const _Machine3DComponent({
    required this.node,
    this.metrics,
    required this.isSelected,
    required this.isBottleneck,
    required this.pulse,
    required this.queueSize,
  });

  @override
  Widget build(BuildContext context) {
    final health = metrics?.healthIndex ?? 1.0;
    // Normalize health to 0-100 if it's 0-1
    final healthPercent = health <= 1.0 ? health * 100 : health;
    final healthColor = healthPercent > 70 ? Colors.greenAccent : (healthPercent > 30 ? Colors.orangeAccent : Colors.redAccent);
    final borderColor = isSelected ? const Color(0xFF00E5FF) : (isBottleneck ? Colors.redAccent : Colors.white24);
    final isCritical = healthPercent <= 30;

    return AnimatedScale(
      scale: isSelected ? 1.15 : 1.0,
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOutCubic,
      child: Transform.translate(
        offset: isCritical 
            ? Offset(math.sin(pulse * math.pi * 8) * 1.5, 0)
            : Offset.zero,
        child: Stack(
          alignment: Alignment.center,
          clipBehavior: Clip.none,
          children: [
            // 3D Cuboid Base
            AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              width: 60, height: 40,
              decoration: BoxDecoration(
                color: const Color(0xFF1A212B),
                border: Border.all(
                  color: isCritical ? Color.lerp(Colors.redAccent, Colors.transparent, pulse)! : borderColor, 
                  width: isSelected ? 2 : 1
                ),
                boxShadow: [
                  if (isBottleneck || isCritical) 
                    BoxShadow(
                      color: (isCritical ? Colors.redAccent : Colors.redAccent).withOpacity(0.5 * pulse), 
                      blurRadius: 15 * pulse, 
                      spreadRadius: 2 * pulse
                    ),
                  if (isSelected) const BoxShadow(color: Color(0xFF00E5FF), blurRadius: 12, spreadRadius: 2),
                ],
              ),
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(node.id, style: const TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 4),
                    // Animated Health Bar
                    Container(
                      width: 40,
                      height: 3,
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(2),
                      ),
                      child: FractionallySizedBox(
                        alignment: Alignment.centerLeft,
                        widthFactor: (healthPercent / 100).clamp(0.0, 1.0),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 500),
                          decoration: BoxDecoration(
                            color: healthColor,
                            borderRadius: BorderRadius.circular(2),
                            boxShadow: [
                              BoxShadow(color: healthColor.withOpacity(0.6), blurRadius: 4),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            
            // Queue Size Badge
            if (queueSize > 0)
              Positioned(
                top: -12,
                right: -12,
                child: AnimatedScale(
                  scale: 1.0 + (pulse * 0.1),
                  duration: Duration.zero,
                  child: Container(
                    padding: const EdgeInsets.all(5),
                    decoration: BoxDecoration(
                      color: Colors.orangeAccent,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(color: Colors.orangeAccent.withOpacity(0.6), blurRadius: 8 * pulse)
                      ],
                    ),
                    child: Text(
                      "$queueSize",
                      style: const TextStyle(color: Colors.black, fontSize: 9, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
              ),
            
            // Float Label
            Transform(
              transform: Matrix4.translationValues(0, -55, 0),
              child: AnimatedOpacity(
                duration: const Duration(milliseconds: 200),
                opacity: isSelected || isCritical ? 1.0 : 0.7,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.black.withOpacity(0.85), 
                    borderRadius: BorderRadius.circular(6), 
                    border: Border.all(color: healthColor.withOpacity(0.5)),
                    boxShadow: const [BoxShadow(color: Colors.black45, blurRadius: 4)],
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text("${healthPercent.toInt()}% HEALTH", style: TextStyle(color: healthColor, fontSize: 8, fontWeight: FontWeight.bold)),
                      if (!node.id.contains("buf"))
                        Text("RUL: ${metrics?.remainingUsefulLife.toInt() ?? 'N/A'}", style: const TextStyle(color: Colors.white70, fontSize: 7)),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GridPainter extends CustomPainter {
  final Color color;
  _GridPainter({required this.color});
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 0.5;
    for (double i = 0; i <= size.width; i += 40) {
      canvas.drawLine(Offset(i, 0), Offset(i, size.height), paint);
    }
    for (double i = 0; i <= size.height; i += 40) {
      canvas.drawLine(Offset(0, i), Offset(size.width, i), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _MiniChartPainter extends CustomPainter {
  final Color color;
  final List<FlSpot> spots;
  
  _MiniChartPainter({required this.color, required this.spots});
  
  @override
  void paint(Canvas canvas, Size size) {
    if (spots.isEmpty) return;

    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    double minX = spots.first.x;
    double maxX = spots.last.x;
    if (maxX == minX) maxX = minX + 1;
    
    double minY = spots.map((s) => s.y).fold(spots.first.y, (a, b) => a < b ? a : b);
    double maxY = spots.map((s) => s.y).fold(spots.first.y, (a, b) => a > b ? a : b);
    if (maxY == minY) {
      maxY = minY + 1;
      minY = minY - 1;
    }

    final path = Path();
    for (int i = 0; i < spots.length; i++) {
      final spot = spots[i];
      final x = (spot.x - minX) / (maxX - minX) * size.width;
      // Invert Y because canvas Y grows downwards
      final y = size.height - ((spot.y - minY) / (maxY - minY) * size.height);
      
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _MiniChartPainter oldDelegate) => true;
}

class _ProjectedConnectionPainter extends CustomPainter {
  final List<LayoutEdge> edges;
  final List<LayoutNode> nodes;
  final Matrix4 cameraMatrix;
  final List<JobParticle> activeParticles;
  final double globalThroughput;
  final double pulse; // Use for manual flow animation

  _ProjectedConnectionPainter({
    required this.edges,
    required this.nodes,
    required this.cameraMatrix,
    this.activeParticles = const [],
    this.globalThroughput = 0.0,
    required this.pulse,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // Base edge thickness slightly scales with throughput
    final baseThickness = (1.2 + (globalThroughput / 20000)).clamp(1.0, 3.0);
    
    final paint = Paint()
      ..color = const Color(0xFF00E5FF).withOpacity(0.15)
      ..strokeWidth = baseThickness
      ..style = PaintingStyle.stroke;

    final flowPaint = Paint()
      ..color = const Color(0xFF00E5FF).withOpacity(0.4)
      ..strokeWidth = baseThickness * 1.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final particlePaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;

    final glowPaint = Paint()
      ..color = const Color(0xFF00E5FF).withOpacity(0.8)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6)
      ..style = PaintingStyle.fill;

    final centerX = size.width / 2;
    final centerY = size.height / 2;

    Offset project(LayoutNode node) {
      final zOffset = (node.level - 1) * -180.0;
      final vec = v64.Vector4(
        node.position.x - 400,
        node.position.y - 300,
        zOffset - 20,
        1.0,
      );
      final transformed = cameraMatrix.transform(vec);
      final w = transformed.w == 0 ? 1.0 : transformed.w;
      return Offset(centerX + transformed.x / w, centerY + transformed.y / w);
    }

    final nodePositions = <String, Offset>{};
    for (final node in nodes) {
      nodePositions[node.id] = project(node);
    }

    // 1. Draw all edges and "flow" shader effect
    for (final edge in edges) {
      final p1 = nodePositions[edge.fromNode];
      final p2 = nodePositions[edge.toNode];
      
      if (p1 != null && p2 != null) {
        // Draw static base line
        canvas.drawLine(p1, p2, paint);

        // Draw directional flow markers using pulse
        // We calculate 3 segments that move along the line
        for (int i = 0; i < 3; i++) {
          final offset = (pulse + (i / 3.0)) % 1.0;
          final start = Offset.lerp(p1, p2, (offset - 0.1).clamp(0.0, 1.0))!;
          final end = Offset.lerp(p1, p2, offset)!;
          
          if (offset > 0.1) {
             canvas.drawLine(start, end, flowPaint);
          }
        }
      }
    }

    // 2. Draw discrete job particles (actual items moving)
    final now = DateTime.now();
    for (final particle in activeParticles) {
      final p1 = nodePositions[particle.fromNode];
      final p2 = nodePositions[particle.toNode];
      
      if (p1 != null && p2 != null) {
        final elapsed = now.difference(particle.startTime).inMilliseconds;
        final progress = (elapsed / 1500.0).clamp(0.0, 1.0);
        
        if (progress < 1.0) {
          final currentPos = Offset.lerp(p1, p2, progress)!;
          canvas.drawCircle(currentPos, 3, glowPaint);
          canvas.drawCircle(currentPos, 1.5, particlePaint);
        }
      }
    }
  }

  @override
  bool shouldRepaint(covariant _ProjectedConnectionPainter oldDelegate) => true;
}

class CountUpText extends StatefulWidget {
  final double value;
  final int decimals;
  final String suffix;
  final TextStyle style;

  const CountUpText({
    super.key,
    required this.value,
    this.decimals = 0,
    this.suffix = "",
    required this.style,
  });

  @override
  State<CountUpText> createState() => _CountUpTextState();
}

class _CountUpTextState extends State<CountUpText> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;
  double _oldValue = 0;

  @override
  void initState() {
    super.initState();
    _oldValue = widget.value;
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _animation = Tween<double>(begin: _oldValue, end: widget.value).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );
  }

  @override
  void didUpdateWidget(CountUpText oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.value != widget.value) {
      _oldValue = oldWidget.value;
      _animation = Tween<double>(begin: _oldValue, end: widget.value).animate(
        CurvedAnimation(parent: _controller, curve: Curves.easeOut),
      );
      _controller.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animation,
      builder: (context, _) {
        return Text(
          "${_animation.value.toStringAsFixed(widget.decimals)}${widget.suffix}",
          style: widget.style,
        );
      },
    );
  }
}
