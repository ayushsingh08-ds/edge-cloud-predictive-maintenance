import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../components/canvas_area.dart';
import '../components/sidebar_panels.dart';
import '../components/neumorphic_theme.dart';
import '../components/bottom_panel.dart';
import '../providers/layout_provider.dart';
import '../providers/simulation_provider.dart';
import '../models/models.dart';

class LayoutEditorScreen extends StatefulWidget {
  const LayoutEditorScreen({Key? key}) : super(key: key);

  @override
  _LayoutEditorScreenState createState() => _LayoutEditorScreenState();
}

class _LayoutEditorScreenState extends State<LayoutEditorScreen> {
  bool _showDashboard = false;
  bool _isMenuExpanded = false;
  bool _dismissConnectionWarning = false;
  final FocusNode _canvasFocus = FocusNode();

  @override
  void initState() {
    super.initState();
    _canvasFocus.requestFocus();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final layout = Provider.of<LayoutProvider>(context, listen: false);
      final simulation = Provider.of<SimulationProvider>(
        context,
        listen: false,
      );

      layout.initializeCatalog();
      layout.refreshLayout(force: true);
      simulation.initialize();

      // Connect Industrial Routing Pipeline
      simulation.onLayoutChanged = () => layout.refreshLayout(force: true);
      simulation.onRoutingRequest = (candidates) {
        layout.clearRoutingUI();
        for (var edgeId in candidates) {
          layout.highlightEdge(edgeId, isCandidate: true);
        }
      };
      simulation.onRoutingDecision = (edgeId) {
        if (edgeId == null) return;
        layout.clearRoutingUI();
        layout.highlightEdge(edgeId, isActive: true);

        // Auto-clear decision pulse after 1.5s
        Future.delayed(const Duration(milliseconds: 1500), () {
          if (mounted) layout.clearRoutingUI();
        });
      };
    });
  }

  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    final simulation = Provider.of<SimulationProvider>(context);

    // Re-arm the warning overlay once connectivity is restored.
    if (simulation.backendConnected && _dismissConnectionWarning) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        setState(() {
          _dismissConnectionWarning = false;
        });
      });
    }

    // Watch for backend errors - MOVED to listener or handled via overlay to prevent build-loop crashes
    // if (simulation.lastError != null) { ... }

    return CallbackShortcuts(
      bindings: {
        SingleActivator(LogicalKeyboardKey.delete): () =>
            layout.bulkDeleteSelected(),
        SingleActivator(LogicalKeyboardKey.escape): () =>
            layout.cancelProcess(),
        SingleActivator(LogicalKeyboardKey.keyS, control: true): () =>
            layout.refreshLayout(force: true),
      },
      child: Focus(
        autofocus: true,
        focusNode: _canvasFocus,
        child: Scaffold(
          backgroundColor: NeumorphicColors.background(layout.isDarkMode),
          body: Stack(
            children: [
              Column(
                children: [
                  _buildTopBar(context, simulation, layout),
                  Expanded(
                    child: Row(
                      children: [
                        const FactorySidebar(),
                        const Expanded(child: FactoryCanvas()),
                        _buildRightPanel(context),
                      ],
                    ),
                  ),
                  const BottomPanel(),
                ],
              ),
              _buildFloatingTools(context),
              if (layout.activeMode == AppMode.showcase &&
                  simulation.currentScenarioId != null)
                _buildMissionBoard(context, simulation, layout),
              if (!simulation.backendConnected && !_dismissConnectionWarning)
                Positioned.fill(
                  child: Container(
                    color: Colors.black.withOpacity(0.4),
                    child: Center(
                      child: Container(
                        padding: const EdgeInsets.all(24),
                        decoration: NeumorphicTheme.decoration(
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Stack(
                          children: [
                            Positioned(
                              top: 0,
                              right: 0,
                              child: IconButton(
                                tooltip: 'Dismiss warning',
                                icon: const Icon(Icons.close),
                                color: Colors.grey,
                                onPressed: () {
                                  setState(() {
                                    _dismissConnectionWarning = true;
                                  });
                                },
                              ),
                            ),
                            const Padding(
                              padding: EdgeInsets.only(top: 8.0, right: 32.0),
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    Icons.cloud_off,
                                    size: 48,
                                    color: Colors.red,
                                  ),
                                  SizedBox(height: 16),
                                  Text(
                                    'Backend Connection Lost',
                                    style: TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  SizedBox(height: 8),
                                  Text(
                                    'Attempting to reconnect...',
                                    style: TextStyle(color: Colors.grey),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  // I will replace only what's needed for the top bar and dashboard

  Widget _buildFloatingTools(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);

    return Positioned(
      bottom: 85,
      right: 330,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (_isMenuExpanded) ...[
            _buildGlassToolItem(
              icon: Icons.mouse_outlined,
              label: 'Select',
              isActive: layout.currentTool == EditorTool.select,
              onPressed: () => layout.setTool(EditorTool.select),
              delay: 4,
            ),
            _buildGlassToolItem(
              icon: Icons.select_all_outlined,
              label: 'Select All',
              onPressed: () => layout.selectAll(),
              delay: 3,
            ),
            _buildGlassToolItem(
              icon: Icons.add_link_outlined,
              label: 'Join',
              isActive: layout.currentTool == EditorTool.connect,
              onPressed: () => layout.setTool(EditorTool.connect),
              delay: 2,
            ),
            _buildGlassToolItem(
              icon: Icons.link_off_outlined,
              label: 'Break Link',
              isActive: layout.currentTool == EditorTool.deleteEdge,
              onPressed: () => layout.setTool(EditorTool.deleteEdge),
              delay: 1,
            ),
            _buildGlassToolItem(
              icon: Icons.delete_forever_outlined,
              label: 'Bulk Delete',
              onPressed: () => _confirmBulkDelete(context, layout),
              color: Colors.redAccent,
              delay: 0,
              badgeCount: layout.selectedNodeIds.length,
            ),
            _buildGlassToolItem(
              icon: Icons.close_outlined,
              label: 'Cancel',
              onPressed: () => layout.cancelProcess(),
              color: Colors.orangeAccent,
              delay: 0,
            ),
          ],
          const SizedBox(height: 8),
          _buildMainFab(),
        ],
      ),
    );
  }

  void _confirmBulkDelete(BuildContext context, LayoutProvider layout) {
    if (layout.selectedNodeIds.isEmpty) return;

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: NeumorphicColors.background(layout.isDarkMode),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        title: Text(
          'Confirm Deletion',
          style: TextStyle(
            color: NeumorphicColors.accent(layout.isDarkMode),
            fontWeight: FontWeight.bold,
          ),
        ),
        content: Text(
          'Delete ${layout.selectedNodeIds.length} items and all their connections?',
          style: TextStyle(color: NeumorphicColors.text(layout.isDarkMode)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(
              'Cancel',
              style: TextStyle(color: NeumorphicColors.text(layout.isDarkMode)),
            ),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.redAccent,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            onPressed: () async {
              final count = layout.selectedNodeIds.length;
              await layout.bulkDeleteSelected();
              if (context.mounted) {
                Navigator.pop(context);
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  _showUndoSnackbar(context, layout, count);
                });
              }
            },
            child: const Text('Delete', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _showUndoSnackbar(
    BuildContext context,
    LayoutProvider layout,
    int count,
  ) {
    // Clear previous snackbars first for instant feedback
    ScaffoldMessenger.of(context).clearSnackBars();

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Removed $count items'),
        backgroundColor: NeumorphicColors.accent(layout.isDarkMode),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
        width: 320,
        action: SnackBarAction(
          label: 'UNDO',
          textColor: Colors.white,
          onPressed: () {
            layout.undoDelete();
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
          },
        ),
      ),
    );
  }

  Widget _buildMainFab() {
    final layout = Provider.of<LayoutProvider>(context);
    return GestureDetector(
      onTap: () => setState(() => _isMenuExpanded = !_isMenuExpanded),
      child: Container(
        width: 56,
        height: 56,
        decoration:
            NeumorphicTheme.decoration(
              isDark: layout.isDarkMode,
              borderRadius: BorderRadius.circular(28),
            ).copyWith(
              color: _isMenuExpanded
                  ? NeumorphicColors.accent(layout.isDarkMode)
                  : NeumorphicColors.background(layout.isDarkMode),
            ),
        child: Icon(
          _isMenuExpanded ? Icons.close : Icons.edit_outlined,
          color: _isMenuExpanded
              ? Colors.white
              : NeumorphicColors.accent(layout.isDarkMode),
        ),
      ),
    );
  }

  Widget _buildGlassToolItem({
    required IconData icon,
    required String label,
    required VoidCallback onPressed,
    required int delay,
    bool isActive = false,
    Color? color,
    int badgeCount = 0,
  }) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: Duration(milliseconds: 200 + (delay * 40)),
      builder: (context, value, child) {
        return Opacity(
          opacity: value,
          child: Transform.translate(
            offset: Offset(0, 15 * (1 - value)),
            child: Padding(
              padding: const EdgeInsets.only(bottom: 8.0),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: BackdropFilter(
                      filter: ImageFilter.blur(sigmaX: 5, sigmaY: 5),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        color: Colors.white.withOpacity(0.05),
                        child: Text(
                          label,
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.bold,
                            color: NeumorphicColors.text(
                              Provider.of<LayoutProvider>(
                                context,
                                listen: false,
                              ).isDarkMode,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Stack(
                    clipBehavior: Clip.none,
                    children: [
                      NeumorphicButton(
                        padding: 10,
                        borderRadius: 20,
                        onPressed: onPressed,
                        child: Icon(
                          icon,
                          size: 18,
                          color: isActive
                              ? Colors.green
                              : (color ??
                                    NeumorphicColors.accent(
                                      Provider.of<LayoutProvider>(
                                        context,
                                        listen: false,
                                      ).isDarkMode,
                                    )),
                        ),
                      ),
                      if (badgeCount > 0)
                        Positioned(
                          right: -4,
                          top: -4,
                          child: Container(
                            padding: const EdgeInsets.all(4),
                            decoration: const BoxDecoration(
                              color: Colors.redAccent,
                              shape: BoxShape.circle,
                            ),
                            child: Text(
                              badgeCount.toString(),
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 8,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildTopBar(
    BuildContext context,
    SimulationProvider simulation,
    LayoutProvider layout,
  ) {
    return Container(
      height: 72,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: BoxDecoration(
        color: NeumorphicColors.background(layout.isDarkMode),
        border: Border(
          bottom: BorderSide(
            color: layout.isDarkMode ? Colors.white10 : Colors.black12,
            width: 1,
          ),
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Flexible(
            flex: 2,
            child: Row(
              children: [
                Icon(
                  Icons.analytics_outlined,
                  color: NeumorphicColors.accent(layout.isDarkMode),
                  size: 28,
                ),
                const SizedBox(width: 12),
                Flexible(
                  child: Text(
                    layout.activeMode == AppMode.showcase
                        ? 'Digital Twin Showcase'
                        : 'Digital Twin Engineer',
                    style: TextStyle(
                      fontSize: 20, // Slightly reduced to save space
                      fontWeight: FontWeight.w600,
                      color: NeumorphicColors.accent(layout.isDarkMode),
                      letterSpacing: -0.5,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),

          // NEW: Mode Switcher (Engineering / Showcase)
          _buildModeSwitcher(layout),

          // Global KPI Ribbon (The Pill Style)
          if (simulation.globalMetrics != null)
            Flexible(
              flex: 5,
              child: Center(
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: _buildGlobalKPIRibbon(
                    simulation.globalMetrics!,
                    layout.isDarkMode,
                  ),
                ),
              ),
            ),

          Expanded(
            flex: 3,
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    '${simulation.speedMultiplier.toStringAsFixed(0)}x',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: NeumorphicColors.accent(layout.isDarkMode),
                    ),
                  ),
                  const SizedBox(width: 4),
                  _buildSpeedControl(simulation, layout.isDarkMode),
                  const SizedBox(width: 8),
                  _buildControlButton(
                    icon: Icons.view_in_ar_rounded,
                    onPressed: () {
                      // Accessing private _toggleIsometric is tricky, 
                      // but I'll add a public method to LayoutProvider instead for 3D state
                      layout.toggleIsometric();
                    },
                    isDark: layout.isDarkMode,
                    color: layout.isometricMode ? Colors.cyanAccent : null,
                  ),
                  const SizedBox(width: 4),
                  _buildControlButton(
                    icon: Icons.dashboard_customize_rounded,
                    onPressed: () => setState(() => _showDashboard = !_showDashboard),
                    isDark: layout.isDarkMode,
                    color: _showDashboard ? Colors.greenAccent : null,
                  ),
                  const SizedBox(width: 4),
                  IconButton(
                    onPressed: () => layout.toggleDarkMode(),
                    icon: Icon(
                      layout.isDarkMode
                          ? Icons.light_mode
                          : Icons.dark_mode_outlined,
                    ),
                    color: NeumorphicColors.accent(
                      layout.isDarkMode,
                    ).withOpacity(0.8),
                  ),
                  const SizedBox(width: 4),
                  _buildControlButton(
                    icon: simulation.isSimulating
                        ? Icons.pause
                        : Icons.play_arrow_rounded,
                    onPressed: () => simulation.isSimulating
                        ? simulation.stopSimulation()
                        : simulation.startSimulation(),
                    isDark: layout.isDarkMode,
                    color: simulation.isSimulating
                        ? Colors.orangeAccent
                        : Colors.greenAccent,
                  ),
                  const SizedBox(width: 4),
                  _buildControlButton(
                    icon: Icons.refresh_rounded,
                    isDark: layout.isDarkMode,
                    onPressed: () => layout.refreshLayout(force: true),
                  ),
                  const SizedBox(width: 4),
                  _buildControlButton(
                    icon: Icons.grid_view_rounded,
                    isDark: layout.isDarkMode,
                    onPressed: () => layout.autoAlignToGrid(),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGlobalKPIRibbon(GlobalMetrics metrics, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      decoration:
          NeumorphicTheme.decoration(
            isDark: isDark,
            borderRadius: BorderRadius.circular(24),
            color: NeumorphicColors.background(isDark),
          ).copyWith(
            boxShadow: NeumorphicTheme.insetShadows(
              isDark: isDark,
              blurRadius: 12,
              offset: const Offset(4, 4),
            ),
          ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildKPIStat(
            'THROUGHPUT',
            '${metrics.throughput.toStringAsFixed(1)}/hr',
            isDark,
          ),
          _buildVerticalDivider(isDark),
          _buildKPIStat(
            'LEAD TIME',
            '${metrics.leadTime.toStringAsFixed(1)}m',
            isDark,
          ),
          _buildVerticalDivider(isDark),
          _buildKPIStat(
            'AVG UTIL',
            '${(metrics.avgUtilization * 100).toStringAsFixed(0)}%',
            isDark,
          ),
          _buildVerticalDivider(isDark),
          _buildKPIStat(
            'BOTTLENECKS',
            '${metrics.bottlenecks} jobs',
            isDark,
            color: metrics.bottlenecks > 0 ? Colors.redAccent : null,
          ),
          _buildVerticalDivider(isDark),
          _buildKPIStat(
            'WIP',
            '${(metrics.wip / 100).toStringAsFixed(0)}%',
            isDark,
          ),
          _buildVerticalDivider(isDark),
          _buildKPIStat(
            'OEE',
            '${(metrics.oee * 100).toStringAsFixed(0)}%',
            isDark,
          ),
        ],
      ),
    );
  }

  Widget _buildVerticalDivider(bool isDark) => Container(
    width: 1,
    height: 12,
    margin: const EdgeInsets.symmetric(horizontal: 10),
    color: NeumorphicColors.darkShadow(isDark).withOpacity(0.3),
  );

  Widget _buildMissionBoard(
    BuildContext context,
    SimulationProvider simulation,
    LayoutProvider layout,
  ) {
    final scenarioId = simulation.currentScenarioId;
    String missionTitle = "Digital Twin Showcase";
    String missionLogic = "Select a scenario to begin projection.";
    IconData missionIcon = Icons.info_outline_rounded;

    if (scenarioId == 'balanced_baseline') {
      missionTitle = "BASELINE PERFORMANCE";
      missionLogic =
          "Optimizing for steady-state OEE and throughput across parallel tracks.";
      missionIcon = Icons.account_tree_outlined;
    } else if (scenarioId == 'bottleneck_stress') {
      missionTitle = "BOTTLENECK STRESS";
      missionLogic =
          "Watch queue back-pressure build up before the master machine.";
      missionIcon = Icons.speed_outlined;
    } else if (scenarioId == 'failure_prone') {
      missionTitle = "BYPASS STRATEGY";
      missionLogic =
          "Watch the divider bypass the failed machines and manage buffer back-pressure.";
      missionIcon = Icons.warning_amber_outlined;
    } else if (scenarioId == 'dynamic_routing') {
      missionTitle = "DYNAMIC FAIL-OVER";
      missionLogic =
          "Comparing high-speed/fragile paths against robust backup trails.";
      missionIcon = Icons.alt_route_rounded;
    }

    final isDark = layout.isDarkMode;
    return Positioned(
      top: 100,
      left: 20,
      child: Material(
        color: Colors.transparent,
        child: Container(
          width: 300,
          padding: const EdgeInsets.all(16),
          decoration:
              NeumorphicTheme.decoration(
                isDark: isDark,
                borderRadius: BorderRadius.circular(20),
              ).copyWith(
                color: NeumorphicColors.background(isDark).withOpacity(0.95),
                border: Border.all(
                  color: NeumorphicColors.accent(isDark).withOpacity(0.2),
                  width: 1,
                ),
              ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Icon(
                    missionIcon,
                    size: 14,
                    color: NeumorphicColors.accent(isDark),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    missionTitle,
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w900,
                      color: NeumorphicColors.accent(isDark),
                      letterSpacing: 1.1,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                missionLogic,
                style: TextStyle(
                  fontSize: 11,
                  fontStyle: FontStyle.italic,
                  color: NeumorphicColors.text(isDark).withOpacity(0.7),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildModeSwitcher(LayoutProvider layout) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: NeumorphicColors.background(layout.isDarkMode).withOpacity(0.5),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: layout.isDarkMode ? Colors.white10 : Colors.black12,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildModeButton(
            AppMode.showcase,
            'SHOWCASE',
            Icons.auto_awesome_rounded,
            layout,
          ),
          _buildModeButton(
            AppMode.engineering,
            'ENGINEERING',
            Icons.construction_rounded,
            layout,
          ),
        ],
      ),
    );
  }

  Widget _buildModeButton(
    AppMode mode,
    String label,
    IconData icon,
    LayoutProvider layout,
  ) {
    final isActive = layout.activeMode == mode;
    final isDark = layout.isDarkMode;
    return GestureDetector(
      onTap: () => layout.setAppMode(mode),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isActive
              ? NeumorphicColors.accent(isDark)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
          boxShadow: isActive
              ? [
                  BoxShadow(
                    color: NeumorphicColors.accent(isDark).withOpacity(0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ]
              : null,
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 14,
              color: isActive
                  ? Colors.white
                  : NeumorphicColors.text(isDark).withOpacity(0.5),
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w900,
                color: isActive
                    ? Colors.white
                    : NeumorphicColors.text(isDark).withOpacity(0.5),
                letterSpacing: 1.1,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildKPIStat(
    String label,
    String value,
    bool isDark, {
    Color? color,
  }) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 8,
            color: NeumorphicColors.text(isDark).withOpacity(0.5),
            fontWeight: FontWeight.bold,
            letterSpacing: 0.5,
          ),
        ),
        Text(
          value,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            color: color ?? NeumorphicColors.accent(isDark),
          ),
        ),
      ],
    );
  }

  Widget _buildControlButton({
    required IconData icon,
    required VoidCallback onPressed,
    required bool isDark,
    Color? color,
  }) {
    return NeumorphicButton(
      padding: 10,
      borderRadius: 12,
      onPressed: onPressed,
      child: Icon(
        icon,
        size: 20,
        color: color ?? NeumorphicColors.accent(isDark),
      ),
    );
  }

  Widget _buildSpeedControl(SimulationProvider provider, bool isDark) {
    return Container(
      width: 160,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: NeumorphicTheme.decoration(
        isDark: isDark,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(Icons.speed, size: 14, color: NeumorphicColors.accent(isDark)),
          Expanded(
            child: Slider(
              value: provider.speedMultiplier,
              min: 0.5,
              max: 5.0,
              divisions: 9,
              activeColor: NeumorphicColors.accent(isDark),
              onChanged: (value) => provider.setSpeed(value),
            ),
          ),
          Text(
            '${provider.speedMultiplier}x',
            style: TextStyle(
              fontSize: 9,
              fontWeight: FontWeight.bold,
              color: NeumorphicColors.text(isDark),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRightPanel(BuildContext context) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 300),
      child: _showDashboard ? const DashboardPanel() : const PropertiesPanel(),
    );
  }
}

class DashboardPanel extends StatelessWidget {
  const DashboardPanel({Key? key}) : super(key: key);
  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<SimulationProvider>(context);
    final layout = Provider.of<LayoutProvider>(context);
    final activeIds = layout.nodes.map((n) => n.id.toLowerCase()).toSet();
    final machines = provider.machineMetrics.values
        .where((m) => activeIds.contains(m.machineId.toLowerCase()))
        .toList();
    return Container(
      width: 300,
      decoration: NeumorphicTheme.decoration(
        isDark: layout.isDarkMode,
        borderRadius: const BorderRadius.horizontal(left: Radius.circular(24)),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(24.0),
            child: Text(
              'Real-time Dashboard',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: NeumorphicColors.accent(layout.isDarkMode),
              ),
            ),
          ),
          Expanded(
            child: ExcludeSemantics(
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                children: [
                  if (machines.isEmpty)
                    Padding(
                      padding: const EdgeInsets.all(32.0),
                      child: Column(
                        children: [
                          Icon(
                            Icons.sensors_off_rounded,
                            size: 48,
                            color: NeumorphicColors.text(layout.isDarkMode)
                                .withOpacity(0.2),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'No Active Telemetry',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                              color: NeumorphicColors.text(layout.isDarkMode)
                                  .withOpacity(0.4),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Start the simulation or select a machine to view real-time metrics.',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              fontSize: 11,
                              color: NeumorphicColors.text(layout.isDarkMode)
                                  .withOpacity(0.3),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ...machines
                      .map(
                        (machine) => Padding(
                          padding: const EdgeInsets.only(bottom: 16.0),
                          child: NeumorphicCard(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      machine.machineId,
                                      style: TextStyle(
                                        fontWeight: FontWeight.bold,
                                        fontSize: 12,
                                        color: NeumorphicColors.text(
                                          layout.isDarkMode,
                                        ),
                                      ),
                                    ),
                                    _buildStatusDot(machine.status),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                _buildStatRow(
                                  'OEE',
                                  '${(machine.oee * 100).toStringAsFixed(1)}%',
                                  layout.isDarkMode,
                                ),
                                _buildStatRow(
                                  'Load',
                                  '${(machine.load).toStringAsFixed(1)}%',
                                  layout.isDarkMode,
                                ),
                                _buildStatRow(
                                  'Health',
                                  '${(machine.healthIndex).toStringAsFixed(1)}%',
                                  layout.isDarkMode,
                                ),
                                _buildStatRow(
                                  'Risk',
                                  '${(machine.congestionRisk * 100).toStringAsFixed(0)}%',
                                  layout.isDarkMode,
                                  color: machine.congestionRisk > 0.7
                                      ? Colors.red
                                      : (machine.congestionRisk > 0.4
                                            ? Colors.orange
                                            : null),
                                ),

                                // Triple-Trend Sparklines
                                const SizedBox(height: 8),
                                if (provider.healthHistory[machine.machineId] !=
                                    null)
                                  _buildMiniTrend(
                                    'HEALTH',
                                    provider.healthHistory[machine.machineId]!,
                                    Colors.green,
                                    layout.isDarkMode,
                                  ),
                                if (provider.loadHistory[machine.machineId] !=
                                    null)
                                  _buildMiniTrend(
                                    'LOAD',
                                    provider.loadHistory[machine.machineId]!,
                                    Colors.orange,
                                    layout.isDarkMode,
                                  ),
                              ],
                            ),
                          ),
                        ),
                      )
                      .toList(),
                  // Event Log Section
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 16.0),
                    child: Text(
                      'RECENT ALERTS',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: NeumorphicColors.text(layout.isDarkMode),
                        letterSpacing: 1,
                      ),
                    ),
                  ),
                  ...provider.recentAlerts.map((alert) {
                    final message = _readAlertMessage(alert);
                    final severity = _readAlertSeverity(alert);
                    final timestamp = _readAlertTimestamp(alert);

                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8.0),
                      child: Row(
                        children: [
                          Icon(
                            severity == 'critical'
                                ? Icons.error_outline
                                : Icons.warning_amber_rounded,
                            size: 12,
                            color: severity == 'critical'
                                ? Colors.red
                                : Colors.orange,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              message,
                              style: TextStyle(
                                fontSize: 9,
                                color: NeumorphicColors.text(layout.isDarkMode),
                              ),
                            ),
                          ),
                          Text(
                            _safeTime(timestamp),
                            style: TextStyle(
                              fontSize: 8,
                              color: NeumorphicColors.text(
                                layout.isDarkMode,
                              ).withOpacity(0.5),
                            ),
                          ),
                        ],
                      ),
                    );
                  }).toList(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _readAlertMessage(dynamic alert) {
    if (alert is PredictiveAlert) {
      return alert.message.isEmpty ? 'System Notification' : alert.message;
    }
    if (alert is Map) {
      final map = Map<String, dynamic>.from(alert);
      final payload = map['payload'] is Map
          ? Map<String, dynamic>.from(map['payload'])
          : const <String, dynamic>{};
      final raw =
          (map['message'] ??
                  map['reason'] ??
                  payload['message'] ??
                  payload['reason'] ??
                  payload['event'] ??
                  map['event_type'])
              ?.toString()
              .trim();
      if (raw != null && raw.isNotEmpty) {
        return raw;
      }
    }
    return 'System Notification';
  }

  String _readAlertSeverity(dynamic alert) {
    if (alert is PredictiveAlert) {
      return alert.severity.toLowerCase();
    }
    if (alert is Map) {
      final raw = alert['severity']?.toString().toLowerCase();
      if (raw != null && raw.isNotEmpty) {
        return raw;
      }
    }
    return 'warning';
  }

  dynamic _readAlertTimestamp(dynamic alert) {
    if (alert is PredictiveAlert) {
      return alert.timestamp;
    }
    if (alert is Map) {
      return alert['timestamp'];
    }
    return null;
  }

  String _safeTime(dynamic timestamp) {
    if (timestamp == null) return '';
    if (timestamp is num) {
      if (timestamp < 1000000) return 'Env ${timestamp.toStringAsFixed(0)}s';
      // If it looks like a unix epoch
      try {
        final dt = DateTime.fromMillisecondsSinceEpoch(timestamp.toInt());
        return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
      } catch (_) {}
    }

    final s = timestamp.toString();
    if (s.contains('T')) {
      final timePart = s.split('T').last;
      return timePart.substring(0, timePart.length < 5 ? timePart.length : 5);
    }
    // Fallback for short strings that might be times already
    if (s.length <= 5) return s;
    return s.substring(0, s.length < 5 ? s.length : 5);
  }

  Widget _buildMiniTrend(
    String label,
    List<double> data,
    Color color,
    bool isDark,
  ) {
    return Padding(
      padding: const EdgeInsets.only(top: 6.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 7,
              fontWeight: FontWeight.bold,
              color: NeumorphicColors.text(isDark).withOpacity(0.5),
            ),
          ),
          SizedBox(
            height: 20,
            width: double.infinity,
            child: CustomPaint(
              painter: SparklinePainter(
                data: data,
                color: color.withOpacity(0.4),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusDot(MachineStatus status) {
    Color color = Colors.green;
    if (status == MachineStatus.failed) color = Colors.red;
    if (status == MachineStatus.idle) color = Colors.grey;
    return Icon(Icons.circle, color: color, size: 8);
  }

  Widget _buildStatRow(
    String label,
    String value,
    bool isDark, {
    Color? color,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
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
              fontSize: 10,
              fontWeight: FontWeight.bold,
              color: color ?? NeumorphicColors.accent(isDark),
            ),
          ),
        ],
      ),
    );
  }
}

class SparklinePainter extends CustomPainter {
  final List<double> data;
  final Color color;

  SparklinePainter({required this.data, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (data.length < 2) return;

    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final path = Path();
    final xStep = size.width / (data.length - 1);

    // Normalize data (expecting 0-100 range for health)
    const minY = 0.0;
    const maxY = 100.0;

    for (int i = 0; i < data.length; i++) {
      final x = i * xStep;
      final normalizedY = (data[i] - minY) / (maxY - minY);
      final y = size.height - (normalizedY * size.height);

      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }

    canvas.drawPath(path, paint);

    // Fill subtle gradient area
    final fillPath = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();

    final fillPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [color.withOpacity(0.1), Colors.transparent],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));

    canvas.drawPath(fillPath, fillPaint);
  }

  @override
  bool shouldRepaint(covariant SparklinePainter oldDelegate) => true;
}
