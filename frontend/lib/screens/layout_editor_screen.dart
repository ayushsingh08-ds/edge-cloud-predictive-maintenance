import 'dart:ui';
import 'package:flutter/material.dart';
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

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<LayoutProvider>(context, listen: false).initializeCatalog();
      Provider.of<SimulationProvider>(context, listen: false).initialize();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: NeumorphicColors.background,
      body: Stack(
        children: [
          Column(
            children: [
              _buildTopBar(context),
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
        ],
      ),
    );
  }

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
        backgroundColor: NeumorphicColors.background,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        title: const Text('Confirm Deletion', style: TextStyle(color: NeumorphicColors.accent, fontWeight: FontWeight.bold)),
        content: Text('Delete ${layout.selectedNodeIds.length} items and all their connections?', style: const TextStyle(color: NeumorphicColors.text)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel', style: TextStyle(color: NeumorphicColors.text))),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
            onPressed: () {
              final count = layout.selectedNodeIds.length;
              layout.bulkDeleteSelected();
              Navigator.pop(context);
              _showUndoSnackbar(context, layout, count);
            },
            child: const Text('Delete', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _showUndoSnackbar(BuildContext context, LayoutProvider layout, int count) {
    // Clear previous snackbars first for instant feedback
    ScaffoldMessenger.of(context).clearSnackBars();
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Removed $count items'),
        backgroundColor: NeumorphicColors.accent,
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating, // Floating behavior often handles dismissal better
        width: 320, // Keep it compact
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
    return GestureDetector(
      onTap: () => setState(() => _isMenuExpanded = !_isMenuExpanded),
      child: Container(
        width: 56,
        height: 56,
        decoration: NeumorphicTheme.decoration(borderRadius: BorderRadius.circular(28)).copyWith(
          color: _isMenuExpanded ? NeumorphicColors.accent : NeumorphicColors.background,
        ),
        child: Icon(_isMenuExpanded ? Icons.close : Icons.edit_outlined, color: _isMenuExpanded ? Colors.white : NeumorphicColors.accent),
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
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        color: Colors.white.withOpacity(0.05),
                        child: Text(label, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: NeumorphicColors.text)),
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
                        child: Icon(icon, size: 18, color: isActive ? Colors.green : (color ?? NeumorphicColors.accent)),
                      ),
                      if (badgeCount > 0)
                        Positioned(
                          right: -4,
                          top: -4,
                          child: Container(
                            padding: const EdgeInsets.all(4),
                            decoration: const BoxDecoration(color: Colors.redAccent, shape: BoxShape.circle),
                            child: Text(badgeCount.toString(), style: const TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold)),
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

  Widget _buildTopBar(BuildContext context) {
    final simulation = Provider.of<SimulationProvider>(context);
    final layout = Provider.of<LayoutProvider>(context);
    return Container(
      height: 70,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: NeumorphicTheme.decoration(borderRadius: BorderRadius.zero),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(children: [const Icon(Icons.factory_outlined, color: NeumorphicColors.accent, size: 28), const SizedBox(width: 12), const Text('Digital Twin Editor', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: NeumorphicColors.accent))]),
          Row(
            children: [
              _buildControlButton(icon: Icons.zoom_in, onPressed: () {}),
              const SizedBox(width: 8),
              _buildControlButton(icon: Icons.zoom_out, onPressed: () {}),
              const SizedBox(width: 16),
              _buildControlButton(
                icon: simulation.isSimulating ? Icons.pause : Icons.play_arrow,
                onPressed: () => simulation.isSimulating ? simulation.stopSimulation() : simulation.startSimulation(),
              ),
              const SizedBox(width: 16),
              _buildControlButton(icon: Icons.refresh, onPressed: () => layout.refreshLayout()),
              const SizedBox(width: 16),
              _buildControlButton(icon: _showDashboard ? Icons.edit_note : Icons.dashboard_outlined, onPressed: () => setState(() => _showDashboard = !_showDashboard)),
              const SizedBox(width: 24),
              _buildSpeedControl(simulation),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildControlButton({required IconData icon, required VoidCallback onPressed}) {
    return NeumorphicButton(padding: 10, borderRadius: 12, onPressed: onPressed, child: Icon(icon, size: 20, color: NeumorphicColors.accent));
  }

  Widget _buildSpeedControl(SimulationProvider provider) {
    return Container(
      width: 180,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: NeumorphicTheme.decoration(borderRadius: BorderRadius.circular(16)),
      child: Row(children: [const Icon(Icons.speed, size: 16, color: NeumorphicColors.accent), Expanded(child: Slider(value: provider.speedMultiplier, min: 0.5, max: 5.0, divisions: 9, activeColor: NeumorphicColors.accent, onChanged: (value) => provider.setSpeed(value))), Text('${provider.speedMultiplier}x', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: NeumorphicColors.text))]),
    );
  }

  Widget _buildRightPanel(BuildContext context) {
    return AnimatedSwitcher(duration: const Duration(milliseconds: 300), child: _showDashboard ? const DashboardPanel() : const PropertiesPanel());
  }
}

class DashboardPanel extends StatelessWidget {
  const DashboardPanel({Key? key}) : super(key: key);
  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<SimulationProvider>(context);
    final machines = provider.machineMetrics.values.toList();
    return Container(
      width: 300,
      decoration: NeumorphicTheme.decoration(borderRadius: const BorderRadius.horizontal(left: Radius.circular(24))),
      child: Column(
        children: [
          const Padding(padding: EdgeInsets.all(24.0), child: Text('Real-time Dashboard', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: NeumorphicColors.accent))),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: machines.length,
              itemBuilder: (context, index) {
                final machine = machines[index];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 16.0),
                  child: NeumorphicCard(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(machine.machineId, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)), _buildStatusDot(machine.status)]),
                        const SizedBox(height: 8),
                        _buildStatRow('OEE', '${(machine.oee * 100).toStringAsFixed(1)}%'),
                        _buildStatRow('Health', '${(machine.healthIndex).toStringAsFixed(1)}%'),
                        _buildStatRow('RUL', '${machine.remainingUsefulLife.toStringAsFixed(0)}h'),
                      ],
                    ),
                  ),
                );
              },
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
  Widget _buildStatRow(String label, String value) {
    return Padding(padding: const EdgeInsets.symmetric(vertical: 2.0), child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(label, style: const TextStyle(fontSize: 10, color: NeumorphicColors.text)), Text(value, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: NeumorphicColors.accent))]));
  }
}
