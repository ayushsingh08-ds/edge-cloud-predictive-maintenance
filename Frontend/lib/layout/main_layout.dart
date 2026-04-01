import 'package:flutter/material.dart';
import 'package:frontend/theme/app_theme.dart';
import 'package:frontend/widgets/sidebar.dart';
import 'package:frontend/widgets/topbar.dart';


class MainLayout extends StatelessWidget {
  final Widget child;
  final String title;
  final int selectedIndex;
  final Function(int) onItemSelected;
  final bool isSimulationRunning;
  final VoidCallback onStartSimulation;
  final VoidCallback onSettings;
  final VoidCallback onProfile;

  const MainLayout({
    super.key,
    required this.child,
    this.title = 'Dashboard',
    required this.selectedIndex,
    required this.onItemSelected,
    required this.isSimulationRunning,
    required this.onStartSimulation,
    required this.onSettings,
    required this.onProfile,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.creamBackground,
      body: Column(
        children: [
          TopBar(
            isSimulationRunning: isSimulationRunning,
            onStartSimulation: onStartSimulation,
            onSettings: onSettings,
            onProfile: onProfile,
          ),
          Expanded(
            child: Row(
              children: [
                Sidebar(
                  selectedIndex: selectedIndex,
                  onItemSelected: onItemSelected,
                ),
                Expanded(
                  child: Container(
                    margin: const EdgeInsets.fromLTRB(0, 0, 24, 24),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(32),
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.softShadow.withOpacity(0.5),
                          offset: const Offset(0, 8),
                          blurRadius: 24,
                        ),
                      ],
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(32),
                      child: child,
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
}
